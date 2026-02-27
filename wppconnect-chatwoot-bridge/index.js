const express = require('express');
const bodyParser = require('body-parser');
const axios = require('axios');
const winston = require('winston');
const FormData = require('form-data');
const mime = require('mime-types');
require('dotenv').config();

// ========================================
// CONFIGURAÇÃO DE LOGS
// ========================================
const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.printf(({ timestamp, level, message, ...meta }) => {
      return `[${timestamp}] ${level.toUpperCase()}: ${message} ${Object.keys(meta).length ? JSON.stringify(meta) : ''}`;
    })
  ),
  transports: [
    new winston.transports.Console()
  ]
});

// ========================================
// CONFIGURAÇÃO DO SERVIDOR
// ========================================
const app = express();
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

const PORT = process.env.PORT || 3500;

// Configurações
const config = {
  wppconnect: {
    url: process.env.WPPCONNECT_URL,
    session: process.env.WPPCONNECT_SESSION,
    token: process.env.WPPCONNECT_TOKEN,
    secret: process.env.WPPCONNECT_SECRET || process.env.WPPCONNECT_SECRET_KEY || process.env.WPP_SECRET_KEY || process.env.WPP_SECRET
  },
  chatwoot: {
    url: process.env.CHATWOOT_URL,
    accountId: process.env.CHATWOOT_ACCOUNT_ID,
    inboxId: process.env.CHATWOOT_INBOX_ID,
    apiToken: process.env.CHATWOOT_API_TOKEN
  }
};

const MEDIA_TYPES = new Set([
  'audio',
  'document',
  'file',
  'gif',
  'image',
  'ptt',
  'sticker',
  'video',
  'voice'
]);

const DATA_URI_REGEX = /^data:([^;]+);base64,([A-Za-z0-9+/=\r\n]+)$/;

function getMessageId(message) {
  if (!message) return null;
  if (typeof message.id === 'string') return message.id;
  if (message.id?._serialized) return message.id._serialized;
  if (message.key?.id) return message.key.id;
  return null;
}

function buildWppHeaders(custom = {}) {
  const headers = {
    Authorization: `Bearer ${config.wppconnect.token}`,
    'Content-Type': 'application/json',
    ...custom
  };

  if (config.wppconnect.secret) {
    headers['x-secret-key'] = config.wppconnect.secret;
  }

  return headers;
}

function collectAttachmentsFromPayload(payload) {
  const seen = new Set();
  const result = [];

  const register = (item) => {
    if (!item || typeof item !== 'object') {
      return;
    }

    if (result.includes(item)) {
      return;
    }

    const keys = Object.keys(item).sort();
    const signature = item.id || item.file_url || item.url || item.data_url || `${keys.join('|')}-${item.filename || item.file_name || ''}`;

    if (signature && seen.has(signature)) {
      return;
    }

    if (signature) {
      seen.add(signature);
    }

    result.push(item);
  };

  const scan = (value) => {
    if (!value) {
      return;
    }

    if (Array.isArray(value)) {
      value.forEach(scan);
      return;
    }

    if (typeof value === 'object') {
      const maybeAttachment = value.data_url || value.file_url || value.url || value.base64 || value.base64Ptt || value.file_data;

      if (maybeAttachment || value.filename || value.file_name || value.name || value.id) {
        register(value);
        return;
      }

      Object.values(value).forEach(scan);
      return;
    }

    if (typeof value === 'string') {
      if (value.startsWith('http') || value.startsWith('/')) {
        register({ file_url: value });
        return;
      }

      const parsed = extractBase64Payload(value);
      if (parsed) {
        register({ data_url: value, mimetype: parsed.mimeType });
      }
    }
  };

  const candidates = [
    payload?.attachments,
    payload?.message?.attachments,
    payload?.content_attributes?.attachments,
    payload?.content_attributes?.files,
    payload?.message?.content_attributes?.attachments,
    payload?.message?.content_attributes?.files,
    payload?.message?.content_attributes?.documents,
    payload?.message?.content_attributes?.audios,
    payload?.message?.content_attributes?.data,
    payload?.message?.content_attributes?.payload
  ];

  candidates.forEach(scan);
  return result;
}

// Constantes para sanitização de logs
const MAX_DEPTH = 3;
const MAX_STRING = 200;

// Cache para evitar duplicação de mensagens (Chatwoot dispara message_created + message_updated)
const processedOutgoingMessages = new Set();
const CACHE_TTL_MS = 10000; // 10 segundos

function sanitizeForLog(value, depth = 0) {
  if (depth > MAX_DEPTH) {
    return '[Object depth exceeded]';
  }

  if (value === null || value === undefined) {
    return value;
  }

  if (typeof value === 'string') {
    if (value.length <= MAX_STRING) {
      return value;
    }
    return `${value.slice(0, MAX_STRING)}... [len=${value.length}]`;
  }

  if (Array.isArray(value)) {
    return value.slice(0, 5).map(item => sanitizeForLog(item, depth + 1));
  }

  if (typeof value === 'object') {
    const sanitized = {};
    Object.entries(value).forEach(([key, val]) => {
      sanitized[key] = sanitizeForLog(val, depth + 1);
    });
    return sanitized;
  }

  return value;
}

async function fetchMessageFromChatwoot(conversationId, messageId) {
  if (!conversationId || !messageId) {
    return null;
  }

  const headers = {
    'api_access_token': config.chatwoot.apiToken,
    'Content-Type': 'application/json'
  };

  const conversationKey = typeof conversationId === 'object' ? conversationId.id : conversationId;
  const messageKey = typeof messageId === 'object' ? messageId.id : messageId;

  const baseUrl = `${config.chatwoot.url}/api/v1/accounts/${config.chatwoot.accountId}/conversations/${conversationKey}`;

  try {
    const directResponse = await axios.get(`${baseUrl}/messages/${messageKey}`, { headers });
    return directResponse.data;
  } catch (error) {
    logger.debug('Direct Chatwoot message fetch failed', {
      conversationId: conversationKey,
      messageId: messageKey,
      error: error.response?.status || error.message
    });
  }

  try {
    const listResponse = await axios.get(`${baseUrl}/messages`, {
      params: {
        page: 1,
        per_page: 15,
        sort: '-created_at'
      },
      headers
    });

    const messages = listResponse.data?.data || listResponse.data?.payload || [];
    return messages.find(msg => (msg.id === messageKey) || (msg.external_id === messageKey));
  } catch (error) {
    logger.warn('Failed to list Chatwoot messages for attachment lookup', {
      conversationId: conversationKey,
      messageId: messageKey,
      error: error.response?.status || error.message
    });
  }

  return null;
}

async function fetchConversationAttachments(conversationId, options = {}) {
  if (!conversationId) {
    return [];
  }

  const headers = {
    'api_access_token': config.chatwoot.apiToken,
    'Content-Type': 'application/json'
  };

  const conversationKey = typeof conversationId === 'object' ? conversationId.id : conversationId;
  const baseUrl = `${config.chatwoot.url}/api/v1/accounts/${config.chatwoot.accountId}/conversations/${conversationKey}/attachments`;

  try {
    const response = await axios.get(baseUrl, {
      params: {
        per_page: options.perPage || 50,
        page: options.page || 1
      },
      headers
    });

    let attachments = response.data?.payload || response.data?.data || [];

    if (!Array.isArray(attachments) && Array.isArray(attachments?.data)) {
      attachments = attachments.data;
    }

    attachments = Array.isArray(attachments) ? attachments : [];

    const nextPage = Number(response.data?.meta?.next_page || 0);
    const currentPage = Number(options.page || 1);
    if (options.allowPagination && nextPage && nextPage > currentPage) {
      const remaining = await fetchConversationAttachments(conversationId, {
        ...options,
        page: nextPage
      });
      attachments = attachments.concat(remaining);
    }

    return attachments;
  } catch (error) {
    logger.warn('Failed to fetch Chatwoot conversation attachments', {
      conversationId: conversationKey,
      error: error.response?.status || error.message
    });
    return [];
  }
}

function extractFilenameFromUrl(url) {
  if (!url || typeof url !== 'string') {
    return null;
  }

  try {
    const resolved = url.startsWith('http') ? new URL(url) : new URL(url, config.chatwoot.url);
    const pathname = resolved.pathname || '';
    const segments = pathname.split('/').filter(Boolean);
    if (segments.length === 0) {
      return null;
    }
    return decodeURIComponent(segments[segments.length - 1]);
  } catch (error) {
    logger.debug('Unable to extract filename from URL', { url, error: error.message });
    return null;
  }
}

async function fetchAttachmentsForMessage(conversationId, messageId) {
  const attachments = await fetchConversationAttachments(conversationId, { allowPagination: true });
  if (!attachments.length) {
    logger.debug('Conversation attachments list is empty', {
      conversationId: typeof conversationId === 'object' ? conversationId.id : conversationId
    });
    return [];
  }

  logger.debug('Conversation attachments fetched', {
    conversationId: typeof conversationId === 'object' ? conversationId.id : conversationId,
    total: attachments.length
  });

  const messageKey = typeof messageId === 'object' ? messageId.id : messageId;

  const filtered = attachments.filter((item) => {
    const candidateId = item?.message_id ?? item?.messageId;
    if (candidateId === undefined || candidateId === null) {
      return false;
    }
    return String(candidateId) === String(messageKey);
  }).map((item) => ({
    ...item,
    file_url: item?.data_url || item?.file_url || item?.url,
    filename: item?.file_name || item?.filename || extractFilenameFromUrl(item?.data_url || item?.file_url || '')
  }));

  if (filtered.length > 0) {
    logger.debug('Conversation attachment fallback matched items', {
      conversationId: typeof conversationId === 'object' ? conversationId.id : conversationId,
      messageId: messageKey,
      count: filtered.length
    });
  } else {
    logger.debug('No attachments matched message from conversation list', {
      conversationId: typeof conversationId === 'object' ? conversationId.id : conversationId,
      messageId: messageKey
    });
  }

  return filtered;
}

function isMediaMessage(message) {
  if (!message) return false;
  if (message.isMedia || message.isDocument || message.mimetype || message.mimeType) {
    return true;
  }
  const msgType = (message.type || '').toLowerCase();
  if (MEDIA_TYPES.has(msgType)) {
    return true;
  }

  const possiblePayload = typeof message.body === 'string' ? message.body.trim() : '';
  if (possiblePayload.length > 1000 && /^[A-Za-z0-9+/=\r\n]+$/.test(possiblePayload)) {
    return true;
  }

  if (DATA_URI_REGEX.test(possiblePayload)) {
    return true;
  }

  return false;
}

function extractBase64Payload(rawValue) {
  if (!rawValue || typeof rawValue !== 'string') {
    return null;
  }

  const cleaned = rawValue.replace(/\r?\n/g, '');
  const base64Match = cleaned.match(DATA_URI_REGEX);

  if (base64Match) {
    return {
      mimeType: base64Match[1],
      base64: base64Match[2]
    };
  }

  if (/^[A-Za-z0-9+/=]+$/.test(cleaned)) {
    return {
      mimeType: null,
      base64: cleaned
    };
  }

  return null;
}

function ensureFilename(filename, mimeType, fallbackPrefix = 'wpp-media') {
  const trimmed = (filename || '').trim();
  if (trimmed) {
    return trimmed;
  }
  const extension = mime.extension(mimeType || '') || 'bin';
  return `${fallbackPrefix}-${Date.now()}.${extension}`;
}

function ensureMimeType(currentMime, filename) {
  if (currentMime) {
    return currentMime;
  }
  return mime.lookup(filename || '') || 'application/octet-stream';
}

async function downloadMediaFromWPP(message) {
  const messageId = typeof message === 'string' ? message : getMessageId(message);

  if (!messageId) {
    logger.warn('downloadMediaFromWPP called without message id');
    return null;
  }

  // Try to get full quality media instead of thumbnail
  const attempts = [
    {
      method: 'post',
      url: `${config.wppconnect.url}/api/${config.wppconnect.session}/download-media`,
      data: { 
        messageId,
        full: true // Request full quality
      }
    },
    {
      method: 'get',
      url: `${config.wppconnect.url}/api/${config.wppconnect.session}/download-media/${encodeURIComponent(messageId)}`
    },
    {
      method: 'post',
      url: `${config.wppconnect.url}/api/${config.wppconnect.session}/download-media`,
      data: { messageId }
    }
  ];

  for (const attempt of attempts) {
    try {
      const response = await axios({
        method: attempt.method,
        url: attempt.url,
        data: attempt.data,
        timeout: 60000, // Increased timeout for larger files
        maxContentLength: Infinity,
        maxBodyLength: Infinity,
        headers: buildWppHeaders()
      });

      let payload = response.data?.response || response.data?.result || response.data;

      if (Array.isArray(payload)) {
        payload = payload[0];
      }

      if (!payload || typeof payload !== 'object') {
        continue;
      }

      const nestedPayload = payload.media || payload.fileResult || payload;
      const base64Value = nestedPayload.base64 || nestedPayload.file || nestedPayload.data;

      if (!base64Value) {
        continue;
      }

      logger.debug('Media downloaded from WPP', {
        messageId,
        size: base64Value.length,
        mimetype: nestedPayload.mimetype || payload.mimetype,
        attemptUrl: attempt.url
      });

      return {
        base64: base64Value,
        mimetype: nestedPayload.mimetype || nestedPayload.mimeType || payload.mimetype || payload.mimeType,
        filename: nestedPayload.filename || nestedPayload.fileName || nestedPayload.name || payload.filename || payload.fileName || payload.name
      };
    } catch (error) {
      logger.warn('Error downloading media from WPPConnect', {
        messageId,
        attempt: attempt.url,
        error: error.response?.data || error.message
      });
    }
  }

  return null;
}

async function buildAttachmentFromWPPMessage(message) {
  try {
    // Prioritize mediaData over body for full quality
    const mediaDataBase64 = message.mediaData?.data || message.mediaData?.base64;
    const bodyBase64 = message.body;
    
    const inlineData = extractBase64Payload(mediaDataBase64) || extractBase64Payload(bodyBase64);
    let base64Content = inlineData?.base64;
    let mimeType = message.mimetype || message.mimeType || inlineData?.mimeType || message.mediaData?.mimetype;
    let filename = message.filename || message.fileName || message.mediaData?.filename;

    // Always download full version for documents (PDF, DOC, etc) since body contains only thumbnail
    // Also download for images if data is too small (likely a thumbnail)
    const isDocument = message.type === 'document' || message.type === 'ptt' || 
                       mimeType?.includes('pdf') || mimeType?.includes('document') ||
                       mimeType?.includes('msword') || mimeType?.includes('officedocument');
    
    const shouldDownload = !base64Content || 
                          isDocument || 
                          (base64Content.length < 10000 && message.type === 'image');
    
    if (shouldDownload) {
      logger.debug('Downloading full quality media', {
        messageId: getMessageId(message),
        hasInlineData: !!base64Content,
        inlineDataSize: base64Content?.length || 0,
        type: message.type,
        isDocument,
        mimeType
      });
      
      const downloaded = await downloadMediaFromWPP(message);
      if (downloaded) {
        const parsed = extractBase64Payload(downloaded.base64);
        if (parsed) {
          base64Content = parsed.base64;
          mimeType = mimeType || downloaded.mimetype || parsed.mimeType;
        } else {
          // Use downloaded base64 directly if it's not data URL
          base64Content = downloaded.base64;
          mimeType = mimeType || downloaded.mimetype;
        }
        filename = filename || downloaded.filename;
      }
    }

    if (!base64Content) {
      logger.warn('No media payload found for message', {
        messageId: getMessageId(message),
        hasMediaData: !!message.mediaData,
        hasBody: !!message.body,
        type: message.type
      });
      return null;
    }

    const buffer = Buffer.from(base64Content, 'base64');
    const finalFilename = ensureFilename(filename, mimeType);
    const finalMimeType = ensureMimeType(mimeType, finalFilename);

    logger.debug('Attachment built from WPP message', {
      messageId: getMessageId(message),
      bufferSize: buffer.length,
      filename: finalFilename,
      mimetype: finalMimeType
    });

    return {
      buffer,
      filename: finalFilename,
      mimetype: finalMimeType
    };
  } catch (error) {
    logger.error('Failed to build attachment from WPP message', {
      messageId: getMessageId(message),
      error: error.message
    });
    return null;
  }
}

async function mapWPPMessageToChatwootPayload(message) {
  const media = isMediaMessage(message);
  const attachments = [];

  if (media) {
    const attachment = await buildAttachmentFromWPPMessage(message);
    if (attachment) {
      attachments.push(attachment);
    }
  }

  const hasAttachment = attachments.length > 0;
  const rawContent = media ? (message.caption || '') : (message.body || message.content || '');
  let content = rawContent || (media && hasAttachment ? 'Media received' : rawContent);

  const trimmedContent = (content || '').trim();
  const looksLikeBase64 = DATA_URI_REGEX.test(trimmedContent) || (trimmedContent.length > 1000 && /^[A-Za-z0-9+/=\r\n]+$/.test(trimmedContent));

  if (media && (!content || content.startsWith('data:') || looksLikeBase64)) {
    content = hasAttachment ? 'Media received' : 'Media message received';
  }

  const rawTimestamp = Number(message.timestamp || Date.now());
  const timestampMs = rawTimestamp > 1000000000000 ? rawTimestamp : rawTimestamp * 1000;

  return {
    content,
    type: message.type || 'text',
    attachments,
    contentAttributes: {
      wppconnect_message_id: getMessageId(message),
      timestamp: timestampMs,
      mimetype: message.mimetype || message.mimeType || (hasAttachment ? attachments[0].mimetype : undefined),
      filename: message.filename || message.fileName || (hasAttachment ? attachments[0].filename : undefined),
      isMedia: media
    }
  };
}

async function downloadChatwootAttachment(url) {
  if (!url) {
    return null;
  }

  try {
    let resolvedUrl = url;
    
    // Replace localhost with Docker container name
    resolvedUrl = resolvedUrl.replace('http://localhost:3000', config.chatwoot.url);
    resolvedUrl = resolvedUrl.replace('https://localhost:3000', config.chatwoot.url);
    
    const baseChatwootUrl = config.chatwoot.url || '';
    if (url.startsWith('/')) {
      resolvedUrl = `${baseChatwootUrl}${url}`;
    }

    const headers = {};
    if (baseChatwootUrl && resolvedUrl.startsWith(baseChatwootUrl) && config.chatwoot.apiToken) {
      headers['api_access_token'] = config.chatwoot.apiToken;
      headers['Authorization'] = `Bearer ${config.chatwoot.apiToken}`;
    }

    const response = await axios.get(resolvedUrl, {
      responseType: 'arraybuffer',
      timeout: 60000,
      headers
    });

    return {
      buffer: Buffer.from(response.data),
      mimeType: response.headers['content-type']
    };
  } catch (error) {
    logger.error('Failed to download Chatwoot attachment', {
      url,
      error: error.response?.data || error.message
    });
    return null;
  }
}

async function sendAttachmentsToWPP(phone, attachments, caption) {
  if (!attachments || attachments.length === 0) {
    return false;
  }

  logger.debug('sendAttachmentsToWPP called', {
    phone,
    attachmentCount: attachments.length,
    caption
  });

  let sentAny = false;
  const normalizedCaption = typeof caption === 'string' ? caption : '';

  for (let index = 0; index < attachments.length; index += 1) {
    const attachment = attachments[index];
    
    logger.debug('Processing attachment', {
      index,
      attachmentKeys: Object.keys(attachment),
      filename: attachment?.file_name || attachment?.filename || attachment?.name,
      hasFileUrl: !!attachment?.file_url,
      hasDataUrl: !!attachment?.data_url,
      hasBase64: !!attachment?.base64,
      mimeType: attachment?.content_type || attachment?.mimetype || attachment?.type
    });
    
    const filenameHint = attachment?.file_name || attachment?.filename || attachment?.name;
    let mimeType = attachment?.content_type || attachment?.mimetype || attachment?.type;
    let base64Content = null;

    const inlineCandidates = [
      attachment?.base64,
      attachment?.data,
      attachment?.data_url,
      attachment?.file_data,
      attachment?.payload,
      attachment?.base64Ptt
    ];

    for (const candidate of inlineCandidates) {
      if (typeof candidate !== 'string' || candidate.length === 0) {
        continue;
      }

      const parsed = extractBase64Payload(candidate.trim());
      if (parsed) {
        base64Content = parsed.base64;
        mimeType = mimeType || parsed.mimeType;
        break;
      }
    }

    let downloadResult = null;
    if (!base64Content) {
      const attachmentUrl = attachment?.file_url || attachment?.data_url || attachment?.url;
      downloadResult = await downloadChatwootAttachment(attachmentUrl);

      if (!downloadResult) {
        logger.warn('Unable to retrieve attachment content', {
          phone,
          attachmentIndex: index,
          attachmentKeys: Object.keys(attachment)
        });
        continue;
      }

      logger.debug('Downloaded attachment buffer', {
        bufferLength: downloadResult.buffer.length,
        mimeType: downloadResult.mimeType
      });

      base64Content = downloadResult.buffer.toString('base64');
      mimeType = ensureMimeType(mimeType || downloadResult.mimeType, filenameHint);
      
      logger.debug('Encoded attachment to base64', {
        base64Length: base64Content.length,
        mimeType
      });
    } else {
      mimeType = ensureMimeType(mimeType, filenameHint);
    }

    const filename = ensureFilename(filenameHint, mimeType, 'chatwoot-attachment');

    const isVoiceNote = mimeType === 'audio/ogg' || mimeType === 'audio/opus' || attachment?.file_type === 'audio';
    const endpoint = isVoiceNote ? 'send-voice-base64' : 'send-file-base64';
    
    // Add data URI prefix for WPPConnect
    const base64WithPrefix = `data:${mimeType};base64,${base64Content}`;
    
    const payload = {
      phone,
      filename
    };

    if (isVoiceNote) {
      payload.base64Ptt = base64WithPrefix;
    } else {
      payload.base64 = base64WithPrefix;
      if (normalizedCaption && index === 0) {
        payload.caption = normalizedCaption;
      }
    }

    try {
      await axios.post(
        `${config.wppconnect.url}/api/${config.wppconnect.session}/${endpoint}`,
        payload,
        {
          timeout: 60000,
          headers: buildWppHeaders()
        }
      );
      sentAny = true;
      logger.info('Attachment sent to WPPConnect', {
        phone,
        endpoint,
        filename,
        mimeType
      });
    } catch (error) {
      logger.error('Error sending attachment to WPPConnect', {
        phone,
        endpoint,
        filename,
        error: error.response?.data || error.message
      });
    }
  }

  return sentAny;
}

// ========================================
// FUNÇÕES AUXILIARES
// ========================================

/**
 * Formata número de telefone para padrão Chatwoot
 * @param {string} number - Número do WPPConnect (ex: 5511999999999@c.us)
 * @returns {string} - Número formatado (ex: +5511999999999)
 */
function formatPhoneNumber(number) {
  // Remove @c.us, @g.us, etc
  const cleaned = number.replace(/@.*$/, '');
  // Adiciona + no início se não tiver
  return cleaned.startsWith('+') ? cleaned : `+${cleaned}`;
}

/**
 * Busca contato por ID no Chatwoot
 */
async function getContactById(contactId) {
  try {
    const response = await axios.get(
      `${config.chatwoot.url}/api/v1/accounts/${config.chatwoot.accountId}/contacts/${contactId}`,
      {
        headers: {
          'api_access_token': config.chatwoot.apiToken,
          'Content-Type': 'application/json'
        }
      }
    );
    return response.data.payload;
  } catch (error) {
    logger.error('Error getting contact by ID', { contactId, error: error.message });
    throw error;
  }
}

/**
 * Busca ou cria contato no Chatwoot
 */
async function getOrCreateContact(phoneNumber, name) {
  try {
    const formattedNumber = formatPhoneNumber(phoneNumber);
    
    // Buscar contato existente
    const searchResponse = await axios.get(
      `${config.chatwoot.url}/api/v1/accounts/${config.chatwoot.accountId}/contacts/search`,
      {
        params: { q: formattedNumber },
        headers: {
          'api_access_token': config.chatwoot.apiToken,
          'Content-Type': 'application/json'
        }
      }
    );

    if (searchResponse.data.payload && searchResponse.data.payload.length > 0) {
      logger.info('Contact found', { phoneNumber: formattedNumber, contactId: searchResponse.data.payload[0].id });
      return searchResponse.data.payload[0];
    }

    // Criar novo contato
    const createResponse = await axios.post(
      `${config.chatwoot.url}/api/v1/accounts/${config.chatwoot.accountId}/contacts`,
      {
        inbox_id: config.chatwoot.inboxId,
        name: name || formattedNumber,
        phone_number: formattedNumber,
        identifier: formattedNumber
      },
      {
        headers: {
          'api_access_token': config.chatwoot.apiToken,
          'Content-Type': 'application/json'
        }
      }
    );

    logger.info('Contact created', { phoneNumber: formattedNumber, contactId: createResponse.data.payload.contact.id });
    return createResponse.data.payload.contact;

  } catch (error) {
    logger.error('Error in getOrCreateContact', {
      phoneNumber,
      error: error.response?.data || error.message
    });
    throw error;
  }
}

/**
 * Busca ou cria conversa no Chatwoot
 */
async function getOrCreateConversation(contactId, phoneNumber) {
  try {
    const formattedNumber = formatPhoneNumber(phoneNumber);

    // Buscar conversas abertas do contato
    const response = await axios.get(
      `${config.chatwoot.url}/api/v1/accounts/${config.chatwoot.accountId}/conversations`,
      {
        params: {
          inbox_id: config.chatwoot.inboxId,
          status: 'open'
        },
        headers: {
          'api_access_token': config.chatwoot.apiToken,
          'Content-Type': 'application/json'
        }
      }
    );

    // Procurar conversa do contato
    const conversations = response.data.payload || response.data.data?.payload || [];
    const existingConversation = conversations.find(
      conv => conv.meta?.sender?.phone_number === formattedNumber
    );

    if (existingConversation) {
      logger.info('Conversation found', { contactId, conversationId: existingConversation.id });
      return existingConversation;
    }

    // Buscar o contact_inbox para pegar o source_id correto
    const contactData = typeof contactId === 'object' ? contactId : await getContactById(contactId);
    const contactInbox = contactData.contact_inboxes?.find(ci => ci.inbox.id == config.chatwoot.inboxId);
    
    if (!contactInbox) {
      throw new Error('Contact inbox not found for this inbox');
    }

    // Criar nova conversa usando o source_id do contact_inbox
    const createResponse = await axios.post(
      `${config.chatwoot.url}/api/v1/accounts/${config.chatwoot.accountId}/conversations`,
      {
        source_id: contactInbox.source_id,
        inbox_id: config.chatwoot.inboxId,
        contact_id: contactData.id,
        status: 'open'
      },
      {
        headers: {
          'api_access_token': config.chatwoot.apiToken,
          'Content-Type': 'application/json'
        }
      }
    );

    logger.info('Conversation created', { contactId: contactData.id, conversationId: createResponse.data.id });
    return createResponse.data;

  } catch (error) {
    logger.error('Error in getOrCreateConversation', {
      contactId,
      error: error.response?.data || error.message
    });
    throw error;
  }
}

/**
 * Envia mensagem para o Chatwoot
 */
async function sendMessageToChatwoot(conversationId, message, messageType = 'incoming') {
  try {
    const msgObj = typeof message === 'string'
      ? { content: message, type: 'text' }
      : message;

    const attachments = Array.isArray(msgObj.attachments)
      ? msgObj.attachments.filter(item => item && item.buffer && item.filename)
      : [];

    const contentAttributes = msgObj.contentAttributes || {};
    const baseUrl = `${config.chatwoot.url}/api/v1/accounts/${config.chatwoot.accountId}/conversations/${conversationId}/messages`;

    if (attachments.length > 0) {
      const formData = new FormData();
      formData.append('content', msgObj.content || '');
      formData.append('message_type', messageType);
      formData.append('private', 'false');
      formData.append('content_type', 'text');

      if (Object.keys(contentAttributes).length > 0) {
        formData.append('content_attributes', JSON.stringify(contentAttributes));
      }

      attachments.forEach(attachment => {
        formData.append('attachments[]', attachment.buffer, {
          filename: attachment.filename,
          contentType: attachment.mimetype
        });
      });

      const response = await axios.post(baseUrl, formData, {
        maxContentLength: Infinity,
        maxBodyLength: Infinity,
        headers: {
          ...formData.getHeaders(),
          'api_access_token': config.chatwoot.apiToken
        }
      });

      logger.info('Message with attachment sent to Chatwoot', { conversationId, messageId: response.data.id });
    }

    const payload = {
      content: msgObj.content || msgObj.body || msgObj.text || '',
      message_type: messageType,
      private: false,
      content_type: 'text'
    };

    if (Object.keys(contentAttributes).length > 0) {
      payload.content_attributes = { ...contentAttributes };
    }

    const response = await axios.post(baseUrl, payload, {
      headers: {
        'api_access_token': config.chatwoot.apiToken,
        'Content-Type': 'application/json'
      }
    });

    logger.info('Message sent to Chatwoot', { conversationId, messageId: response.data.id });
    return response.data;

  } catch (error) {
    logger.error('Error sending message to Chatwoot', {
      conversationId,
      error: error.response?.data || error.message
    });
    throw error;
  }
}

// ========================================
// ROTAS DA API
// ========================================

/**
 * Health Check
 */
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    config: {
      wppconnect: !!config.wppconnect.url,
      chatwoot: !!config.chatwoot.url
    }
  });
});

/**
 * Webhook do WPPConnect - Recebe mensagens
 */
app.post('/webhook/wppconnect', async (req, res) => {
  try {
    const { event, data } = req.body;
    
    logger.info('Webhook received from WPPConnect', { event, from: data?.from });

    // Processar apenas mensagens recebidas
    if (event !== 'onMessage' && event !== 'onAnyMessage') {
      return res.json({ status: 'ignored', reason: 'not a message event' });
    }

    // Ignorar mensagens próprias
    if (data.fromMe) {
      return res.json({ status: 'ignored', reason: 'message from me' });
    }

    // Ignorar mensagens de grupos (opcional)
    if (data.isGroupMsg) {
      logger.info('Ignoring group message');
      return res.json({ status: 'ignored', reason: 'group message' });
    }

    // Extrair dados
    const phoneNumber = data.from || data.chatId;
    const senderName = data.notifyName || data.author || phoneNumber;
    // 1. Buscar ou criar contato
    const contact = await getOrCreateContact(phoneNumber, senderName);

    // 2. Buscar ou criar conversa
    const conversation = await getOrCreateConversation(contact.id, phoneNumber);

    // 3. Enviar mensagem para Chatwoot
    const chatwootMessage = await mapWPPMessageToChatwootPayload({
      ...data,
      body: data.body || data.content || '',
      caption: data.caption
    });

    await sendMessageToChatwoot(conversation.id, chatwootMessage, 'incoming');

    res.json({
      status: 'success',
      contactId: contact.id,
      conversationId: conversation.id
    });

  } catch (error) {
    logger.error('Error processing webhook', {
      error: error.response?.data || error.message,
      body: req.body
    });
    res.status(500).json({
      status: 'error',
      message: error.message
    });
  }
});

/**
 * Webhook do Chatwoot - Envia respostas de volta ao WhatsApp
 */
app.post('/webhook/chatwoot', async (req, res) => {
  try {
    const { event, message_type, conversation } = req.body;
    // Trim trailing newlines from Chatwoot content
    const rawContent = req.body.content ?? req.body.message?.content ?? '';
    const content = rawContent.replace(/\n+$/, '');

    logger.info('Webhook received from Chatwoot', {
      event,
      message_type
    });

    logger.debug('Chatwoot webhook payload snapshot', sanitizeForLog({
      keys: Object.keys(req.body || {}),
      messageKeys: Object.keys(req.body.message || {}),
      payload: req.body
    }));

    // Skip processing for non-relevant events
    if (event !== 'message_created' || message_type !== 'outgoing') {
      return res.json({ status: 'ignored' });
    }

    // Deduplication check - Chatwoot fires multiple events for same message
    const messageId = req.body.id || req.body.message?.id;
    logger.info('Deduplication check', { 
      messageId, 
      hasInCache: processedOutgoingMessages.has(messageId),
      cacheSize: processedOutgoingMessages.size,
      bodyId: req.body.id,
      messageObjId: req.body.message?.id
    });
    
    if (!messageId) {
      logger.warn('No message ID found in webhook payload', { payload: req.body });
      return res.json({ status: 'error', message: 'no message id' });
    }

    if (processedOutgoingMessages.has(messageId)) {
      logger.info('❌ Duplicate message BLOCKED', { messageId, event });
      return res.json({ status: 'duplicate_ignored', messageId });
    }

    // Add to processed cache
    processedOutgoingMessages.add(messageId);
    logger.info('✅ Message added to dedup cache', { messageId, cacheSize: processedOutgoingMessages.size });
    
    // Auto-cleanup after TTL
    setTimeout(() => {
      processedOutgoingMessages.delete(messageId);
      logger.debug('Message removed from dedup cache', { messageId });
    }, CACHE_TTL_MS);

    logger.debug('Raw webhook body for attachment analysis', {
      hasAttachments: !!req.body.attachments,
      attachmentsType: Array.isArray(req.body.attachments) ? 'array' : typeof req.body.attachments,
      attachmentsLength: req.body.attachments?.length,
      hasMessage: !!req.body.message,
      messageAttachments: req.body.message?.attachments?.length,
      contentType: req.body.content_type,
      contentAttributes: req.body.content_attributes
    });

    let attachments = collectAttachmentsFromPayload(req.body);
    
    logger.debug('Attachments collected from payload', {
      count: attachments.length,
      attachments: attachments.map(a => ({
        keys: Object.keys(a),
        hasFileUrl: !!a.file_url,
        hasDataUrl: !!a.data_url,
        hasBase64: !!a.base64,
        filename: a.filename || a.file_name,
        mimeType: a.mimetype || a.content_type
      }))
    });

    if (attachments.length === 0) {
      const fetchedMessage = await fetchMessageFromChatwoot(conversation?.id || req.body.conversation_id, req.body.message?.id || req.body.id);
      if (fetchedMessage) {
        logger.debug('Fetched Chatwoot message for attachment lookup', sanitizeForLog({
          id: fetchedMessage.id,
          attachments: fetchedMessage.attachments,
          content_attributes: fetchedMessage.content_attributes
        }));

        const fetchedAttachments = collectAttachmentsFromPayload({
          attachments: fetchedMessage.attachments,
          message: fetchedMessage,
          content_attributes: fetchedMessage.content_attributes
        });
        if (fetchedAttachments.length > 0) {
          attachments = fetchedAttachments;
        } else {
          logger.debug('Fetched Chatwoot message has no detectable attachments', {
            conversationId: conversation?.id || req.body.conversation_id,
            messageId: req.body.message?.id || req.body.id
          });
        }
      } else {
        logger.debug('No Chatwoot message found during attachment lookup', {
          conversationId: conversation?.id || req.body.conversation_id,
          messageId: req.body.message?.id || req.body.id
        });
      }
    }

    if (attachments.length === 0) {
      const fallbackAttachments = await fetchAttachmentsForMessage(conversation?.id || req.body.conversation_id, req.body.message?.id || req.body.id);
      if (fallbackAttachments.length > 0) {
        attachments = fallbackAttachments;
      } else {
        logger.debug('Conversation attachments fallback returned no matches', {
          conversationId: conversation?.id || req.body.conversation_id,
          messageId: req.body.message?.id || req.body.id
        });
      }
    }

    if (attachments.length > 0) {
      const sanitized = attachments.slice(0, 3).map((attachment, index) => ({
        index,
        keys: Object.keys(attachment),
        fileType: attachment.file_type || attachment.type,
        contentType: attachment.content_type || attachment.mimetype,
        hasDataUrl: typeof attachment.data_url === 'string',
        dataLength: attachment.data_url?.length || attachment.data?.length || attachment.base64?.length || 0,
        fileUrl: attachment.file_url || attachment.url || null,
        fileName: attachment.file_name || attachment.filename || attachment.name || null
      }));
      logger.debug('Detected attachments from Chatwoot', { count: attachments.length, sample: sanitized });
    }

    // Log conversation object to debug
    logger.debug('Conversation object received', sanitizeForLog({
      conversation: conversation,
      conversationKeys: conversation ? Object.keys(conversation) : [],
      hasMeta: !!conversation?.meta,
      metaKeys: conversation?.meta ? Object.keys(conversation.meta) : []
    }));

    // Try to get phone number from conversation meta
    let phoneNumber = conversation?.meta?.sender?.phone_number;
    
    // If not found, try to fetch conversation from Chatwoot
    if (!phoneNumber && (conversation?.id || req.body.conversation_id)) {
      logger.info('Phone number not in meta, fetching conversation from Chatwoot');
      try {
        const conversationId = conversation?.id || req.body.conversation_id;
        const response = await axios.get(
          `${config.chatwoot.url}/api/v1/accounts/${config.chatwoot.accountId}/conversations/${conversationId}`,
          {
            headers: {
              'api_access_token': config.chatwoot.apiToken,
              'Content-Type': 'application/json'
            }
          }
        );
        
        phoneNumber = response.data?.meta?.sender?.phone_number;
        logger.info('Phone number retrieved from Chatwoot API', { phoneNumber });
      } catch (error) {
        logger.error('Failed to fetch conversation from Chatwoot', {
          error: error.response?.data || error.message
        });
      }
    }
    
    if (!phoneNumber) {
      logger.warn('No phone number found in conversation', sanitizeForLog({
        conversationId: conversation?.id || req.body.conversation_id,
        conversationMeta: conversation?.meta
      }));
      return res.json({ status: 'error', message: 'no phone number' });
    }

    const wppNumber = phoneNumber.replace('+', '') + '@c.us';
    let attachmentSent = false;
    let textResponse = null;

    if (attachments.length > 0) {
      logger.info('Attempting to send attachments to WPP', {
        wppNumber,
        attachmentCount: attachments.length,
        caption: content
      });
      attachmentSent = await sendAttachmentsToWPP(wppNumber, attachments, content);
      logger.info('Attachment send result', { attachmentSent, wppNumber });
    } else {
      logger.debug('No attachments to send', { wppNumber, hasContent: !!content });
    }

    const shouldSendText = (!attachmentSent && attachments.length > 0 && content) || (attachments.length === 0 && content);

    if (shouldSendText) {
      textResponse = await axios.post(
        `${config.wppconnect.url}/api/${config.wppconnect.session}/send-message`,
        {
          phone: wppNumber,
          message: content,
          isGroup: false
        },
        {
          headers: buildWppHeaders()
        }
      );

      logger.info('Text message sent to WPPConnect', { phoneNumber: wppNumber });
    }

    res.json({
      status: 'success',
      attachments_sent: attachmentSent,
      text_sent: !!textResponse,
      wppconnect_response: textResponse?.data
    });

  } catch (error) {
    logger.error('Error sending message via WPPConnect', {
      error: error.response?.data || error.message
    });
    res.status(500).json({
      status: 'error',
      message: error.message
    });
  }
});

// ========================================
// INICIALIZAÇÃO
// ========================================

// ========================================
// POLLING DE MENSAGENS DO WPPCONNECT
// ========================================
let lastMessageTimestamp = Date.now();
const processedMessageIds = new Set();

async function pollWPPConnectMessages() {
  try {
    logger.debug('Polling WPPConnect for new messages...');
    
    // Buscar todas as conversas com count para pegar mensagens
    const response = await axios.post(
      `${config.wppconnect.url}/api/${config.wppconnect.session}/list-chats`,
      {
        count: 10  // Últimas 10 mensagens de cada chat
      },
      {
        headers: buildWppHeaders()
      }
    );

    logger.debug('Polling response received', { 
      hasData: !!response.data, 
      isArray: Array.isArray(response.data),
      chatsCount: Array.isArray(response.data) ? response.data.length : 0
    });

    if (!response.data || !Array.isArray(response.data)) {
      logger.debug('No data or not an array, skipping');
      return;
    }

    // Processar apenas chats de usuários individuais (não grupos) com mensagens não lidas
    let processedCount = 0;
    for (const chat of response.data) {
      // Ignorar grupos
      if (chat.isGroup) continue;
      
      // Processar apenas chats com mensagens não lidas
      if (!chat.unreadCount || chat.unreadCount === 0) continue;
      
      // Limitar a 5 chats por vez para não sobrecarregar
      if (processedCount >= 5) break;
      
      logger.debug('Processing chat with unread messages', { 
        chatId: chat.id?._serialized || chat.id, 
        unreadCount: chat.unreadCount 
      });
      
      try {
        // Buscar mensagens desse chat específico
        const chatId = chat.id?._serialized || chat.id;
        logger.debug('Fetching messages for chat', { chatId });
        
        const messagesResponse = await axios.get(
          `${config.wppconnect.url}/api/${config.wppconnect.session}/all-messages-in-chat/${encodeURIComponent(chatId)}`,
          {
            headers: buildWppHeaders(),
            timeout: 10000  // 10 segundos de timeout
          }
        );
        
        logger.debug('Messages fetched', { 
          chatId,
          hasData: !!messagesResponse.data,
          isArray: Array.isArray(messagesResponse.data),
          hasResponse: !!messagesResponse.data?.response,
          responseIsArray: Array.isArray(messagesResponse.data?.response),
          count: Array.isArray(messagesResponse.data?.response) ? messagesResponse.data.response.length : 0
        });
        
        // A API retorna { status, response: [...messages] }
        const messagesArray = messagesResponse.data?.response || messagesResponse.data;
        
        if (!messagesArray || !Array.isArray(messagesArray)) {
          logger.debug('No valid messages data, skipping chat', { chatId });
          continue;
        }
        
        // Processar últimas 5 mensagens
        const messages = messagesArray.slice(-5);
        logger.debug('Processing messages', { chatId, messagesCount: messages.length });
        
        for (const msg of messages) {
          // Ignorar mensagens já processadas
          if (processedMessageIds.has(msg.id)) continue;
          
          // Ignorar mensagens próprias
          if (msg.fromMe) continue;
          
          // Ignorar mensagens antigas (mais de 1 hora)
          const messageTime = msg.timestamp * 1000;
          if (Date.now() - messageTime > 3600000) continue;
          
          // Marcar como processada
          processedMessageIds.add(msg.id);
          
          // Limpar cache se muito grande
          if (processedMessageIds.size > 1000) {
            const arr = Array.from(processedMessageIds);
            arr.slice(0, 500).forEach(id => processedMessageIds.delete(id));
          }
          
          logger.info('New message detected via polling', { 
            from: msg.from || msg.chatId,
            body: msg.body?.substring(0, 50)
          });
          
          // Processar a mensagem
          try {
            const phoneNumber = msg.from || msg.chatId;
            const formattedPhone = formatPhoneNumber(phoneNumber);
            
            // Criar ou obter contato
            const contactId = await getOrCreateContact(formattedPhone, msg.notifyName || msg.author || formattedPhone);
            
            // Criar ou obter conversa
            const conversation = await getOrCreateConversation(contactId, formattedPhone);
            
            // Enviar mensagem para Chatwoot
            const chatwootMessage = await mapWPPMessageToChatwootPayload(msg);
            await sendMessageToChatwoot(conversation.id, chatwootMessage);
            
            logger.info('Message from polling sent to Chatwoot', { conversationId: conversation.id });
          } catch (error) {
            logger.error('Error processing polled message', { error: error.message });
          }
        }
        
        processedCount++;
      } catch (chatError) {
        logger.error('Error fetching messages for chat', { 
          chatId: chat.id?._serialized || chat.id,
          error: chatError.message 
        });
      }
    }
    
    if (processedCount > 0) {
      logger.debug(`Processed ${processedCount} chats with unread messages`);
    }
  } catch (error) {
    // Logar todos os erros de polling
    logger.error('Polling error', { 
      error: error.message, 
      status: error.response?.status,
      statusText: error.response?.statusText,
      data: error.response?.data
    });
  }
}

// ========================================
// POLLING DE MENSAGENS OUTGOING DO CHATWOOT
// ========================================
let lastCheckedOutgoingId = 0;

async function pollChatwootOutgoingMessages() {
  try {
    logger.debug('Polling Chatwoot for outgoing messages with attachments...');
    
    // Buscar mensagens recentes da conversa principal (ajustar conversation ID conforme necessário)
    const conversationId = 11; // TODO: Tornar isso dinâmico ou configurável
    
    const response = await axios.get(
      `${config.chatwoot.url}/api/v1/accounts/${config.chatwoot.accountId}/conversations/${conversationId}/messages`,
      {
        headers: {
          'api_access_token': config.chatwoot.apiToken,
          'Content-Type': 'application/json'
        }
      }
    );

    if (!response.data || !response.data.payload) {
      logger.debug('No messages in Chatwoot response');
      return;
    }

    // Filtrar mensagens outgoing (tipo 1) não processadas
    const outgoingMessages = response.data.payload
      .filter(msg => msg.message_type === 1 && msg.id > lastCheckedOutgoingId)
      .sort((a, b) => a.id - b.id); // Processar em ordem

    for (const message of outgoingMessages) {
      // Atualizar ID da última mensagem verificada
      if (message.id > lastCheckedOutgoingId) {
        lastCheckedOutgoingId = message.id;
      }

      // Verificar se já foi processada (evitar duplicação)
      if (processedOutgoingMessages.has(message.id)) {
        logger.debug('Message already processed via webhook', { messageId: message.id });
        continue;
      }

      // Verificar se tem anexos
      if (!message.attachments || message.attachments.length === 0) {
        logger.debug('Outgoing message has no attachments, skipping', { messageId: message.id });
        continue;
      }

      logger.info('📎 Found outgoing message with attachments via polling', {
        messageId: message.id,
        attachmentCount: message.attachments.length,
        content: message.content?.substring(0, 50)
      });

      // Marcar como processada
      processedOutgoingMessages.add(message.id);
      setTimeout(() => {
        processedOutgoingMessages.delete(message.id);
      }, CACHE_TTL_MS);

      // Obter telefone da conversa
      const conversationResponse = await axios.get(
        `${config.chatwoot.url}/api/v1/accounts/${config.chatwoot.accountId}/conversations/${conversationId}`,
        {
          headers: {
            'api_access_token': config.chatwoot.apiToken,
            'Content-Type': 'application/json'
          }
        }
      );

      const phoneNumber = conversationResponse.data?.meta?.sender?.phone_number;
      if (!phoneNumber) {
        logger.warn('No phone number found for conversation', { conversationId });
        continue;
      }

      const wppNumber = phoneNumber.replace('+', '') + '@c.us';

      // Processar anexos
      const attachments = message.attachments.map(att => ({
        file_url: att.data_url,
        file_type: att.file_type,
        file_name: att.data_url ? att.data_url.split('/').pop().split('?')[0] : `attachment_${att.id}`,
        mimetype: att.file_type === 'image' ? 'image/jpeg' : 'application/pdf'
      }));

      logger.info('Sending polled attachments to WPP', {
        wppNumber,
        attachmentCount: attachments.length
      });

      const attachmentSent = await sendAttachmentsToWPP(wppNumber, attachments, message.content || '');
      
      if (!attachmentSent && message.content) {
        // Se falhou enviar anexo mas tem texto, enviar só o texto
        await axios.post(
          `${config.wppconnect.url}/api/${config.wppconnect.session}/send-message`,
          {
            phone: wppNumber,
            message: message.content,
            isGroup: false
          },
          {
            headers: buildWppHeaders()
          }
        );
        logger.info('Sent text fallback for polled message', { messageId: message.id });
      }
    }

  } catch (error) {
    logger.error('Error polling Chatwoot outgoing messages', {
      error: error.message,
      status: error.response?.status
    });
  }
}

// Iniciar polling a cada 2 segundos, mas só após 5 segundos de inicialização
setTimeout(() => {
  logger.info('Starting message polling from WPPConnect (interval: 2s)');
  setInterval(pollWPPConnectMessages, 2000);
  
  logger.info('Starting outgoing message polling from Chatwoot (interval: 3s)');
  setInterval(pollChatwootOutgoingMessages, 3000);
}, 5000);

// ========================================
// INICIAR SERVIDOR
// ========================================
app.listen(PORT, () => {
  logger.info(`🚀 WPPConnect-Chatwoot Bridge started on port ${PORT}`);
  logger.info('Configuration:', {
    wppconnect_url: config.wppconnect.url,
    chatwoot_url: config.chatwoot.url,
    inbox_id: config.chatwoot.inboxId
  });
});

// Graceful shutdown
process.on('SIGTERM', () => {
  logger.info('SIGTERM received, shutting down gracefully');
  process.exit(0);
});

process.on('SIGINT', () => {
  logger.info('SIGINT received, shutting down gracefully');
  process.exit(0);
});
