// POST /api/contact — 接收联系表单，推送到飞书群机器人
// 生产环境变量：FEISHU_WEBHOOK（必填）、FEISHU_SECRET（开启签名校验时必填）
// 本地开发放在 .dev.vars 里

async function feishuSign(secret, timestamp) {
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(`${timestamp}\n${secret}`),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const signature = await crypto.subtle.sign('HMAC', key, new Uint8Array(0));
  return btoa(String.fromCharCode(...new Uint8Array(signature)));
}

function json(body, status = 200) {
  return Response.json(body, { status });
}

export async function onRequestPost(context) {
  const { request, env } = context;

  let data;
  try {
    if ((request.headers.get('content-type') || '').includes('application/json')) {
      data = await request.json();
    } else {
      data = Object.fromEntries((await request.formData()).entries());
    }
  } catch {
    return json({ ok: false, error: '请求格式不正确' }, 400);
  }

  const name = String(data.name || '').trim();
  const email = String(data.email || '').trim();
  const message = String(data.message || '').trim();
  const honeypot = String(data.website || '').trim();

  // 蜜罐字段：正常访客看不到，机器人会填
  if (honeypot) return json({ ok: true });

  if (!name || !email || !message) {
    return json({ ok: false, error: '请填写称呼、邮箱和留言内容' }, 400);
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return json({ ok: false, error: '邮箱格式不正确' }, 400);
  }
  if (name.length > 50 || email.length > 120 || message.length > 2000) {
    return json({ ok: false, error: '内容过长，请精简后再试' }, 400);
  }

  if (!env.FEISHU_WEBHOOK) {
    return json({ ok: false, error: '留言服务尚未配置' }, 500);
  }

  const timestamp = Math.floor(Date.now() / 1000).toString();
  const payload = {
    msg_type: 'interactive',
    card: {
      config: { wide_screen_mode: true },
      header: {
        template: 'carmine',
        title: { tag: 'plain_text', content: 'YJ Atlas · 网站新留言' },
      },
      elements: [
        {
          tag: 'div',
          fields: [
            { is_short: true, text: { tag: 'plain_text', content: `称呼：${name}` } },
            { is_short: true, text: { tag: 'plain_text', content: `邮箱：${email}` } },
          ],
        },
        { tag: 'hr' },
        { tag: 'div', text: { tag: 'plain_text', content: message } },
        { tag: 'hr' },
        {
          tag: 'note',
          elements: [
            {
              tag: 'plain_text',
              content: `来源：yjatlas.com/contact · ${new Date().toLocaleString('zh-CN', {
                timeZone: 'Asia/Shanghai',
                hour12: false,
              })}`,
            },
          ],
        },
      ],
    },
  };

  if (env.FEISHU_SECRET) {
    payload.timestamp = timestamp;
    payload.sign = await feishuSign(env.FEISHU_SECRET, timestamp);
  }

  const res = await fetch(env.FEISHU_WEBHOOK, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  const result = await res.json().catch(() => ({}));
  if (!res.ok || (typeof result.code === 'number' && result.code !== 0)) {
    return json({ ok: false, error: '发送失败，请稍后再试' }, 502);
  }

  return json({ ok: true });
}
