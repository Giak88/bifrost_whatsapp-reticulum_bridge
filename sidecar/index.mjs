// WhatsApp sidecar for the WhatsApp <-> Reticulum/LXMF bridge.
// Talks WhatsApp through Baileys and the Python bridge over a local Unix socket,
// one JSON object per line (NDJSON). Media travel as files in the spool directory.
// Language: BIFROST_LANG=en|it. BIFROST_PAIR_ONLY=1: pair, then exit (used by setup.sh).

import makeWASocket, {
  Browsers,
  DisconnectReason,
  downloadMediaMessage,
  fetchLatestBaileysVersion,
  getContentType,
  isJidGroup,
  normalizeMessageContent,
  useMultiFileAuthState,
} from 'baileys'
import fs from 'node:fs'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import crypto from 'node:crypto'
import P from 'pino'
import qrcode from 'qrcode-terminal'

const BASE = process.env.BIFROST_DIR || path.join(os.homedir(), '.bifrost')
const SOCK = process.env.BIFROST_SOCK || path.join(BASE, 'ipc.sock')
const SPOOL = path.join(BASE, 'spool')
const AUTH = path.join(BASE, 'wa-auth')
const PHONE = (process.env.WA_PHONE || '').replace(/[^0-9]/g, '') // pairing code invece del QR
const MAX_BYTES = Number(process.env.BIFROST_MAX_MB || 16) * 1024 * 1024
const PAIR_ONLY = process.env.BIFROST_PAIR_ONLY === '1'
const LANG = (process.env.BIFROST_LANG || 'en').slice(0, 2) === 'it' ? 'it' : 'en'

const MSG = {
  bridge_up: { en: 'bridge connected', it: 'bridge connesso' },
  bridge_down: { en: 'bridge disconnected', it: 'bridge disconnesso' },
  ipc_on: { en: 'IPC on', it: 'IPC su' },
  bad_line: { en: 'invalid IPC line', it: 'riga IPC non valida' },
  dl_failed: { en: 'download failed: ', it: 'download fallito: ' },
  dl_too_big: { en: 'over the sidecar download limit', it: 'oltre il limite di download del sidecar' },
  contact: { en: 'contact', it: 'contatto' },
  unsupported: { en: 'not supported', it: 'non supportato' },
  unknown_cmd: { en: 'unknown command: ', it: 'comando sconosciuto: ' },
  wa_down: { en: 'WhatsApp not connected', it: 'WhatsApp non connesso' },
  bad_kind: { en: 'unsupported kind: ', it: 'tipo non supportato: ' },
  pair_code: {
    en: 'Pairing code: %s  (WhatsApp > Linked devices > Link with phone number)',
    it: 'Codice di abbinamento: %s  (WhatsApp > Dispositivi collegati > Collega con numero di telefono)',
  },
  scan_qr: { en: 'Scan the QR with WhatsApp > Linked devices:', it: 'Scansiona il QR con WhatsApp > Dispositivi collegati:' },
  connected: { en: 'WhatsApp connected as', it: 'WhatsApp connesso come' },
  logged_out: {
    en: 'WhatsApp session unlinked from the phone: delete the wa-auth folder and pair again',
    it: 'Sessione WhatsApp scollegata dal telefono: cancella la cartella wa-auth e rifai il pairing',
  },
  closed: { en: 'connection closed, reconnecting in 5 s', it: 'connessione chiusa, riconnessione tra 5 s' },
  msg_error: { en: 'message error:', it: 'errore messaggio:' },
  paired: { en: 'Pairing complete, exiting.', it: 'Abbinamento completato, esco.' },
}
const T = k => MSG[k][LANG]

for (const d of [BASE, SPOOL, AUTH]) fs.mkdirSync(d, { recursive: true, mode: 0o700 })

const logger = P({ level: process.env.BIFROST_LOGLEVEL || 'warn' })
const log = (...a) => console.log(new Date().toISOString(), ...a)

// ---------------------------------------------------------------- IPC
let client = null
const backlog = [] // eventi accumulati mentre il bridge non è connesso
const BACKLOG_MAX = 500

function emit(obj) {
  const line = JSON.stringify(obj) + '\n'
  if (client && !client.destroyed) client.write(line)
  else {
    backlog.push(line)
    if (backlog.length > BACKLOG_MAX) backlog.shift()
  }
}

try { if (!PAIR_ONLY) fs.unlinkSync(SOCK) } catch {}
const server = PAIR_ONLY ? null : net.createServer(c => {
  if (client && !client.destroyed) client.destroy()
  client = c
  log(T('bridge_up'))
  emit({ ev: 'status', state: waState, me: sock?.user?.id || null })
  while (backlog.length) c.write(backlog.shift())
  let buf = ''
  c.setEncoding('utf8')
  c.on('data', chunk => {
    buf += chunk
    let i
    while ((i = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, i).trim()
      buf = buf.slice(i + 1)
      if (!line) continue
      let cmd
      try { cmd = JSON.parse(line) } catch { log(T('bad_line')); continue }
      handleCommand(cmd).catch(e => emit({ ev: 'result', req: cmd.req, ok: false, error: String(e?.message || e) }))
    }
  })
  c.on('close', () => { if (client === c) client = null; log(T('bridge_down')) })
  c.on('error', () => {})
})
if (server) server.listen(SOCK, () => { fs.chmodSync(SOCK, 0o600); log(T('ipc_on'), SOCK) })

// ---------------------------------------------------------------- WhatsApp
let sock = null
let waState = 'connecting'
const groupNames = new Map()

async function groupName(jid) {
  if (groupNames.has(jid)) return groupNames.get(jid)
  try {
    const md = await sock.groupMetadata(jid)
    groupNames.set(jid, md.subject)
    return md.subject
  } catch { return jid.split('@')[0] }
}

const MEDIA_KINDS = {
  imageMessage: 'image',
  stickerMessage: 'sticker',
  audioMessage: 'audio',
  videoMessage: 'video',
  documentMessage: 'document',
  documentWithCaptionMessage: 'document',
}

async function onMessage(m) {
  if (!m.message || m.key.fromMe) return
  const chat = m.key.remoteJid
  if (!chat || chat === 'status@broadcast' || chat.endsWith('@newsletter')) return

  const content = normalizeMessageContent(m.message)
  let type = getContentType(content)
  if (!type || type === 'protocolMessage' || type === 'senderKeyDistributionMessage' || type === 'reactionMessage') return
  let inner = content[type]
  if (type === 'documentWithCaptionMessage') inner = inner?.message?.documentMessage

  const isGroup = !!isJidGroup(chat)
  const ev = {
    ev: 'msg',
    id: m.key.id,
    chat,
    is_group: isGroup,
    chat_name: isGroup ? await groupName(chat) : (m.pushName || chat.split('@')[0]),
    sender: isGroup ? (m.key.participant || '') : chat,
    sender_name: m.pushName || '',
    ts: Number(m.messageTimestamp || Date.now() / 1000),
    kind: 'text',
    text: '',
  }

  if (type === 'conversation') ev.text = content.conversation
  else if (type === 'extendedTextMessage') ev.text = inner?.text || ''
  else if (MEDIA_KINDS[type]) {
    ev.kind = MEDIA_KINDS[type]
    ev.text = inner?.caption || ''
    ev.mime = inner?.mimetype || ''
    ev.filename = inner?.fileName || ''
    ev.size = Number(inner?.fileLength || 0)
    ev.seconds = Number(inner?.seconds || 0)
    ev.ptt = !!inner?.ptt
    if (ev.size <= MAX_BYTES) {
      try {
        const data = await downloadMediaMessage(m, 'buffer', {}, { logger, reuploadRequest: sock.updateMediaMessage })
        const p = path.join(SPOOL, `wa-${crypto.randomBytes(6).toString('hex')}`)
        fs.writeFileSync(p, data, { mode: 0o600 })
        ev.path = p
        ev.size = data.length
      } catch (e) {
        ev.error = T('dl_failed') + (e?.message || e)
      }
    } else {
      ev.error = T('dl_too_big')
    }
  } else if (type === 'locationMessage' || type === 'liveLocationMessage') {
    ev.kind = 'location'
    ev.text = `📍 ${inner?.degreesLatitude}, ${inner?.degreesLongitude}` + (inner?.name ? ` (${inner.name})` : '')
  } else if (type === 'contactMessage') {
    ev.text = `👤 ${inner?.displayName || T('contact')}`
  } else {
    ev.kind = 'other'
    ev.text = `[${type} ${T('unsupported')}]`
  }
  emit(ev)
}

async function handleCommand(cmd) {
  if (cmd.cmd === 'ping') return emit({ ev: 'result', req: cmd.req, ok: true })
  if (cmd.cmd !== 'send') throw new Error(T('unknown_cmd') + cmd.cmd)
  if (!sock || waState !== 'open') throw new Error(T('wa_down'))

  let msg
  const readMedia = () => fs.readFileSync(cmd.path)
  switch (cmd.kind) {
    case 'text': msg = { text: cmd.text }; break
    case 'image': msg = { image: readMedia(), caption: cmd.text || undefined, mimetype: cmd.mime || 'image/jpeg' }; break
    case 'audio': msg = { audio: readMedia(), ptt: true, mimetype: 'audio/ogg; codecs=opus' }; break
    case 'video': msg = { video: readMedia(), caption: cmd.text || undefined, mimetype: cmd.mime || 'video/mp4' }; break
    case 'document':
      msg = { document: readMedia(), fileName: cmd.filename || 'file', mimetype: cmd.mime || 'application/octet-stream', caption: cmd.text || undefined }
      break
    default: throw new Error(T('bad_kind') + cmd.kind)
  }
  const sent = await sock.sendMessage(cmd.to, msg)
  if (cmd.path && path.dirname(path.resolve(cmd.path)) === path.resolve(SPOOL)) fs.unlink(cmd.path, () => {})
  emit({ ev: 'result', req: cmd.req, ok: true, id: sent?.key?.id })
}

async function start() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH)
  const { version } = await fetchLatestBaileysVersion().catch(() => ({ version: undefined }))
  sock = makeWASocket({
    version,
    auth: state,
    logger,
    browser: Browsers.ubuntu('Chrome'),
    markOnlineOnConnect: false, // il telefono continua a ricevere le notifiche
    syncFullHistory: false,
  })
  let pairingAsked = false

  sock.ev.on('creds.update', saveCreds)
  sock.ev.on('connection.update', async ({ connection, lastDisconnect, qr }) => {
    if (qr && !sock.authState.creds.registered) {
      if (PHONE && !pairingAsked) {
        pairingAsked = true
        const code = await sock.requestPairingCode(PHONE)
        console.log('\n' + T('pair_code').replace('%s', code) + '\n')
        emit({ ev: 'status', state: 'pairing', code })
      } else if (!PHONE) {
        log(T('scan_qr'))
        qrcode.generate(qr, { small: true })
        emit({ ev: 'status', state: 'qr' })
      }
    }
    if (connection === 'open') {
      waState = 'open'
      log(T('connected'), sock.user?.id)
      emit({ ev: 'status', state: 'open', me: sock.user?.id })
      if (PAIR_ONLY) {
        log(T('paired'))
        setTimeout(() => process.exit(0), 8000) // give the credentials time to be written
      }
    }
    if (connection === 'close') {
      waState = 'close'
      const code = lastDisconnect?.error?.output?.statusCode
      emit({ ev: 'status', state: 'close', code })
      if (code === DisconnectReason.loggedOut) {
        log(T('logged_out'), AUTH)
        process.exit(2)
      }
      log(T('closed'), code)
      setTimeout(start, 5000)
    }
  })
  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    for (const m of messages) log('upsert', type, m.key.remoteJid, 'fromMe=' + !!m.key.fromMe, 'msg=' + (m.message ? Object.keys(m.message).join(',') : 'NULL'))
    if (type !== 'notify') return
    for (const m of messages) await onMessage(m).catch(e => log(T('msg_error'), e?.message || e))
  })
  sock.ev.on('groups.update', ups => { for (const g of ups) if (g.id && g.subject) groupNames.set(g.id, g.subject) })
}

process.on('SIGTERM', () => { try { fs.unlinkSync(SOCK) } catch {}; process.exit(0) })
start()
