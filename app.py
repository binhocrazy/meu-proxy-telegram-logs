from flask import Flask, request, jsonify
import requests, threading, json, html
from datetime import datetime, timezone
from collections import deque

app = Flask(__name__)

# === Config ===
MANYCHAT_WEBHOOK = "https://wh.manychat.com/tgwh/tg0o83f4yg73hfgi73f2g89938g/7135960777/18b23888f78b95bca8b6c0250494e999d8ab694e"
MONITOR_WEBHOOK  = "https://webhook.site/07da2d7a-d596-4047-bca0-e5a188fbb094"

# Buffer em memória (últimas 200 mensagens)
LOG = deque(maxlen=200)

def forward(url, payload):
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[ERRO] ao enviar para {url}: {e}")

def now_iso():
    return datetime.now(timezone.utc).isoformat()

# --- Healthchecks (GET) ---
@app.route("/", methods=["GET"])
def home():
    return "Servidor Flask rodando na Railway ✅", 200

@app.route("/telegram", methods=["GET"])
def telegram_health():
    return "Rota do Telegram ativa ✅", 200

# --- Webhook do Telegram (POST) ---
@app.route("/telegram", methods=["POST"])
def telegram():
    data = request.get_json(silent=True) or {}

    # Extrai um resumo amigável (quando existir)
    msg = data.get("message") or {}
    chat = msg.get("chat") or {}
    user = msg.get("from") or {}

    summary = {
        "ts": now_iso(),
        "chat_id": chat.get("id"),
        "chat_type": chat.get("type"),
        "from_id": user.get("id"),
        "from_name": user.get("first_name"),
        "username": user.get("username"),
        "text": msg.get("text"),
        "payload": data,
    }

    LOG.append(summary)
    print("[TG]", summary["ts"], {"chat_id": summary["chat_id"], "text": summary["text"]})

    # dispara em paralelo para não atrasar a resposta ao Telegram
    threading.Thread(target=forward, args=(MANYCHAT_WEBHOOK, data), daemon=True).start()
    threading.Thread(target=forward, args=(MONITOR_WEBHOOK,  data), daemon=True).start()

    return jsonify({"ok": True}), 200

# --- Dash simples (/logs) ---
@app.route("/logs", methods=["GET"])
def logs():
    items = list(LOG)[-200:][::-1]  # mais recentes primeiro
    rows = []
    for i, it in enumerate(items, 1):
        text = it.get("text")
        text = (text[:140] + "…") if (text and len(text) > 140) else text
        summary = f"[{i:03}] {it.get('ts')} | chat={it.get('chat_id')} | user={it.get('from_name') or it.get('username') or it.get('from_id')} | {text or '(sem texto)'}"
        pretty = html.escape(json.dumps(it.get("payload"), ensure_ascii=False, indent=2))
        rows.append(f"""          <details>
            <summary>{html.escape(summary)}</summary>
            <pre>{pretty}</pre>
          </details>
        """)
    html_page = f"""    <!doctype html>
    <html lang="pt-br">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Logs do Telegram</title>
      <meta http-equiv="refresh" content="10"> <!-- auto-refresh a cada 10s -->
      <style>
        body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; background:#0b0c10; color:#e8edf2; margin:0; }}
        .wrap {{ max-width: 980px; margin: 24px auto; padding: 0 16px; }}
        h1 {{ margin: 0 0 8px; }}
        .meta {{ color:#9aa5b1; margin-bottom: 18px; }}
        details {{ background:#11141a; border:1px solid #232730; border-radius:12px; padding:12px 14px; margin:10px 0; }}
        summary {{ cursor:pointer; outline:none; }}
        pre {{ overflow:auto; background:#0e1116; padding:12px; border-radius:10px; }}
        .topbar a {{ color:#22c55e; text-decoration:none; }}
        .topbar {{ display:flex; gap:12px; align-items:center; margin-bottom:10px; }}
        .pill {{ background:#14321f; border:1px solid #1f6138; color:#bfe8c9; padding:4px 8px; border-radius:999px; font-size:12px; }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="topbar">
          <h1>Logs do Telegram</h1>
          <span class="pill">últimas {len(items)} mensagens</span>
          <a class="pill" href="/telegram">/telegram</a>
          <a class="pill" href="/">/</a>
        </div>
        <div class="meta">Atualiza automaticamente a cada 10s. Clique em um item para ver o JSON completo.</div>
        {''.join(rows) or '<div class="meta">Sem mensagens ainda…</div>'}
      </div>
    </body>
    </html>
    """
    return html_page, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
