import os
import requests
import shutil
import uuid
import time
import sqlite3
from typing import List, Optional
from fastapi import FastAPI, Request, Response, status, File, UploadFile, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "seu_token_aqui")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "seu_token_aqui")
IG_ACCOUNT_ID = "17841400129718274"

ADMIN_USER = os.getenv("ADMIN_USER", "rogerio")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")
AUTH_TOKEN_SECRET = "chave_segura_directdrop_2026"

def verificar_auth(request: Request):
    if request.cookies.get("auth_token") != AUTH_TOKEN_SECRET:
        raise HTTPException(status_code=401, detail="Acesso Negado. Autenticação obrigatória.")

def init_db():
    conn = sqlite3.connect("directdrop.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, sender_id TEXT, comentario TEXT, data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    cursor.execute("CREATE TABLE IF NOT EXISTS regras (id INTEGER PRIMARY KEY AUTOINCREMENT, palavra_chave TEXT, link_produto TEXT, mensagem_dm TEXT, resposta_publica TEXT, post_id TEXT)")
    
    cursor.execute("PRAGMA table_info(regras)")
    columns = [col[1] for col in cursor.fetchall()]
    if "texto_botao" not in columns: cursor.execute("ALTER TABLE regras ADD COLUMN texto_botao TEXT DEFAULT '🚀 Acessar Agora'")
    if "exigir_seguidor" not in columns: cursor.execute("ALTER TABLE regras ADD COLUMN exigir_seguidor INTEGER DEFAULT 0")
        
    conn.commit()
    conn.close()

init_db()

class RegraModel(BaseModel):
    palavra_chave: str
    link_produto: str
    mensagem_dm: str
    resposta_publica: str
    post_id: str
    texto_botao: str = "🚀 Acessar Agora"
    exigir_seguidor: bool = False

# MODELO PARA O COPYWRITER
class PromptIA(BaseModel):
    tema: str
    tipo: str

# ==========================================
# 1. SERVIDOR MCP (INTEGRAÇÃO DE AGENTES IA)
# ==========================================
try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("DirectDrop")

    @mcp.tool()
    def relatorio_leads() -> str:
        """Usa esta ferramenta para consultar a quantidade e os últimos leads capturados pelo sistema."""
        conn = sqlite3.connect("directdrop.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM leads")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT sender_id, comentario FROM leads ORDER BY id DESC LIMIT 5")
        ultimos = cursor.fetchall()
        conn.close()
        res = f"Total de Leads na base: {total}\n\nÚltimos 5 leads capturados:\n"
        for u in ultimos: res += f"- Usuário ID {u[0]} comentou: '{u[1]}'\n"
        return res

    @mcp.tool()
    def relatorio_regras() -> str:
        """Usa esta ferramenta para ver quais automações de palavras-chave estão ativas."""
        conn = sqlite3.connect("directdrop.db")
        cursor = conn.cursor()
        cursor.execute("SELECT palavra_chave, link_produto FROM regras")
        regras = cursor.fetchall()
        conn.close()
        res = f"Existem {len(regras)} regras/fluxos ativos no sistema:\n"
        for r in regras: res += f"- Gatilho '{r[0]}' entrega o link: {r[1]}\n"
        return res

    app.mount("/mcp", mcp.get_asgi_app())
except ImportError:
    print("Biblioteca MCP não instalada. O servidor continuará sem MCP.")

# ==========================================
# 2. COPYWRITER NATIVO (IA NO PAINEL)
# ==========================================
@app.post("/api/gerar-ia", dependencies=[Depends(verificar_auth)])
def gerar_texto_ia(prompt: PromptIA):
    try:
        tema = prompt.tema.strip()
        # Aqui ficará a sua chave de API (OpenAI ou Gemini). Por agora, tem um gerador inteligente nativo:
        if prompt.tipo == "legenda":
            texto = f"🔥 Tudo o que precisa de saber sobre {tema} está aqui!\n\nPreparei um material exclusivo com estratégias práticas para que possa aplicar hoje mesmo.\n\n👇 Quer receber o acesso imediato? Comente 'EU QUERO' aqui em baixo e eu envio-lhe o link diretamente na sua DM! 🚀\n\n#novidade #estrategia #dica"
        else:
            texto = f"Olá! Que excelente ver o seu interesse em {tema} 🎉\n\nComo prometido, aqui está o acesso oficial ao seu material para que possa dar o próximo passo imediato:"
        return {"sucesso": True, "texto": texto}
    except Exception as e:
        return {"sucesso": False, "erro": str(e)}

# ==========================================
# 3. ROTAS DE SISTEMA, LOGIN E FLUXOS
# ==========================================
@app.get("/", response_class=HTMLResponse)
def tela_login(request: Request):
    if request.cookies.get("auth_token") == AUTH_TOKEN_SECRET: return RedirectResponse(url="/painel", status_code=303)
    with open("templates/login.html", "r", encoding="utf-8") as f: return f.read()

@app.post("/api/login")
def fazer_login(response: Response, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USER and password == ADMIN_PASS:
        response.set_cookie(key="auth_token", value=AUTH_TOKEN_SECRET, httponly=True, max_age=86400 * 30)
        return {"sucesso": True}
    return {"sucesso": False, "erro": "Usuário ou senha incorretos!"}

@app.post("/api/logout")
def fazer_logout(response: Response):
    response.delete_cookie("auth_token")
    return {"sucesso": True}

@app.get("/painel", response_class=HTMLResponse)
def painel_visual(request: Request):
    if request.cookies.get("auth_token") != AUTH_TOKEN_SECRET: return RedirectResponse(url="/", status_code=303)
    with open("templates/painel.html", "r", encoding="utf-8") as f: return f.read()

@app.get("/api/conta", dependencies=[Depends(verificar_auth)])
def obter_dados_conta(): return {"username": "@rogerctsales", "foto": "https://ui-avatars.com/api/?name=Rogerio+Sales&background=4F46E5&color=fff", "ig_id": IG_ACCOUNT_ID}

@app.get("/api/feed", dependencies=[Depends(verificar_auth)])
def obter_feed():
    url_media = f"https://graph.facebook.com/v21.0/{IG_ACCOUNT_ID}/media?fields=id,caption,media_type,media_url,thumbnail_url,like_count,comments_count&limit=50&access_token={PAGE_ACCESS_TOKEN}"
    res_media = requests.get(url_media).json()
    if "error" in res_media: return {"sucesso": False, "erro": res_media["error"]["message"]}
    posts = [{"id": i.get("id"), "tipo": i.get("media_type", "IMAGE"), "imagem": i.get("thumbnail_url") if i.get("media_type") == "VIDEO" else i.get("media_url"), "legenda": i.get("caption", "Sem legenda")[:60]+"...", "likes": i.get("like_count", 0), "comentarios": i.get("comments_count", 0)} for i in res_media.get("data", [])]
    return {"sucesso": True, "posts": posts}

@app.get("/api/leads", dependencies=[Depends(verificar_auth)])
def obter_leads():
    conn = sqlite3.connect("directdrop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT sender_id, comentario, data_hora FROM leads ORDER BY id DESC LIMIT 50")
    rows = cursor.fetchall()
    conn.close()
    return {"sucesso": True, "leads": [{"sender_id": r[0], "comentario": r[1], "data": r[2]} for r in rows], "total": len(rows)}

@app.get("/api/regras", dependencies=[Depends(verificar_auth)])
def listar_regras():
    conn = sqlite3.connect("directdrop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, palavra_chave, link_produto, mensagem_dm, resposta_publica, post_id, texto_botao, exigir_seguidor FROM regras ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return {"sucesso": True, "regras": [{"id": r[0], "palavra_chave": r[1], "link_produto": r[2], "mensagem_dm": r[3], "resposta_publica": r[4], "post_id": r[5], "texto_botao": r[6], "exigir_seguidor": bool(r[7])} for r in rows]}

@app.post("/api/regras", dependencies=[Depends(verificar_auth)])
def criar_regra(regra: RegraModel):
    conn = sqlite3.connect("directdrop.db")
    cursor = conn.cursor()
    exige = 1 if regra.exigir_seguidor else 0
    cursor.execute("INSERT INTO regras (palavra_chave, link_produto, mensagem_dm, resposta_publica, post_id, texto_botao, exigir_seguidor) VALUES (?, ?, ?, ?, ?, ?, ?)", (regra.palavra_chave.lower().strip(), regra.link_produto, regra.mensagem_dm, regra.resposta_publica, regra.post_id, regra.texto_botao, exige))
    conn.commit()
    conn.close()
    return {"sucesso": True, "mensagem": "Fluxo criado com sucesso!"}

@app.post("/api/postar", dependencies=[Depends(verificar_auth)])
def publicar_post(request: Request, arquivos: List[UploadFile] = File(...), legenda: str = Form("")):
    try:
        base_url = str(request.base_url).strip("/")
        if base_url.startswith("http://"): base_url = base_url.replace("http://", "https://")
        if len(arquivos) == 1:
            arquivo = arquivos[0]
            ext = arquivo.filename.split(".")[-1].lower()
            is_video = ext in ['mp4', 'mov', 'avi']
            nome_seguro = f"{uuid.uuid4().hex}.{ext}"
            caminho = f"uploads/{nome_seguro}"
            with open(caminho, "wb") as buffer: shutil.copyfileobj(arquivo.file, buffer)
            url_media = f"{base_url}/{caminho}"
            url_container = f"https://graph.facebook.com/v21.0/{IG_ACCOUNT_ID}/media"
            if is_video:
                res_container = requests.post(url_container, data={"media_type": "REELS", "video_url": url_media, "caption": legenda, "access_token": PAGE_ACCESS_TOKEN}).json()
                if "error" in res_container: return {"sucesso": False, "erro": res_container["error"]["message"]}
                creation_id = res_container.get("id")
                status_code = "IN_PROGRESS"
                tentativas = 0
                while status_code != "FINISHED" and tentativas < 12:
                    time.sleep(5)
                    status_code = requests.get(f"https://graph.facebook.com/v21.0/{creation_id}?fields=status_code&access_token={PAGE_ACCESS_TOKEN}").json().get("status_code", "ERROR")
                    if status_code == "ERROR": break
                    tentativas += 1
            else:
                res_container = requests.post(url_container, data={"image_url": url_media, "caption": legenda, "access_token": PAGE_ACCESS_TOKEN}).json()
                if "error" in res_container: return {"sucesso": False, "erro": res_container["error"]["message"]}
                creation_id = res_container.get("id")
                time.sleep(8)
        else:
            children_ids = []
            for arquivo in arquivos:
                ext = arquivo.filename.split(".")[-1]
                caminho = f"uploads/{uuid.uuid4().hex}.{ext}"
                with open(caminho, "wb") as buffer: shutil.copyfileobj(arquivo.file, buffer)
                res_item = requests.post(f"https://graph.facebook.com/v21.0/{IG_ACCOUNT_ID}/media", data={"image_url": f"{base_url}/{caminho}", "is_carousel_item": "true", "access_token": PAGE_ACCESS_TOKEN}).json()
                if "error" in res_item: return {"sucesso": False, "erro": res_item["error"]["message"]}
                children_ids.append(res_item.get("id"))
                time.sleep(3)
            res_carousel = requests.post(f"https://graph.facebook.com/v21.0/{IG_ACCOUNT_ID}/media", data={"media_type": "CAROUSEL", "children": ",".join(children_ids), "caption": legenda, "access_token": PAGE_ACCESS_TOKEN}).json()
            if "error" in res_carousel: return {"sucesso": False, "erro": res_carousel["error"]["message"]}
            creation_id = res_carousel.get("id")
            time.sleep(8)

        res_publish = requests.post(f"https://graph.facebook.com/v21.0/{IG_ACCOUNT_ID}/media_publish", data={"creation_id": creation_id, "access_token": PAGE_ACCESS_TOKEN}).json()
        if "error" in res_publish: return {"sucesso": False, "erro": res_publish["error"]["message"]}
        return {"sucesso": True, "mensagem": "Sucesso! Publicado.", "post_id": creation_id}
    except Exception as e: return {"sucesso": False, "erro": str(e)}

@app.get("/webhook")
def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN: return Response(content=params.get("hub.challenge"), media_type="text/plain", status_code=200)
    return Response(content="Token inválido", status_code=403)

@app.post("/webhook")
async def receive_webhook(request: Request):
    data = await request.json()
    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if change.get("field") == "comments":
                    comment_text = value.get("text", "").lower().strip()
                    sender_id = value.get("from", {}).get("id")
                    comment_id = value.get("id")
                    media_id = str(value.get("media", {}).get("id", ""))
                    
                    conn = sqlite3.connect("directdrop.db")
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, palavra_chave, link_produto, mensagem_dm, resposta_publica, post_id, texto_botao, exigir_seguidor FROM regras")
                    regras = cursor.fetchall()
                    conn.close()
                    for r in regras:
                        regra_id, palavra, link, msg_dm, resp_pub, r_post_id, txt_botao, exigir = r
                        if palavra in comment_text and r_post_id == media_id:
                            if resp_pub: requests.post(f"https://graph.facebook.com/v21.0/{comment_id}/replies", data={"message": resp_pub, "access_token": PAGE_ACCESS_TOKEN}, timeout=10)
                            if exigir:
                                payload_ver = {"recipient": {"comment_id": comment_id}, "message": {"attachment": {"type": "template", "payload": {"template_type": "button", "text": "Olá! Para libertar o seu link, certifique-se de que já segue o nosso perfil e clique no botão abaixo! 👇", "buttons": [{"type": "postback", "title": "✅ Já sigo o perfil!", "payload": f"LIBERAR_LINK_{regra_id}"}]}}}}
                                requests.post(f"https://graph.facebook.com/v21.0/{IG_ACCOUNT_ID}/messages", headers={"Authorization": f"Bearer {PAGE_ACCESS_TOKEN}", "Content-Type": "application/json"}, json=payload_ver, timeout=10)
                            else:
                                enviar_dm_produto(sender_id, comment_id, link, msg_dm, txt_botao)
                            conn = sqlite3.connect("directdrop.db")
                            conn.execute("INSERT INTO leads (sender_id, comentario) VALUES (?, ?)", (str(sender_id), comment_text))
                            conn.commit()
                            conn.close()
                            break

                elif change.get("field") == "messages":
                    postback = value.get("postback", {})
                    sender_id = value.get("sender", {}).get("id")
                    payload_retorno = postback.get("payload", "") if postback else ""
                    if payload_retorno.startswith("LIBERAR_LINK_"):
                        regra_id = payload_retorno.split("_")[-1]
                        conn = sqlite3.connect("directdrop.db")
                        cursor = conn.cursor()
                        cursor.execute("SELECT link_produto, mensagem_dm, texto_botao FROM regras WHERE id = ?", (regra_id,))
                        regra = cursor.fetchone()
                        conn.close()
                        if regra: enviar_dm_produto(sender_id, None, regra[0], regra[1], regra[2])
    except Exception as e: pass
    return Response(content="EVENT_RECEIVED", status_code=200)

def enviar_dm_produto(sender_id: str, comment_id: str, link: str, mensagem: str, texto_botao: str):
    url = f"https://graph.facebook.com/v21.0/{IG_ACCOUNT_ID}/messages"
    headers = {"Authorization": f"Bearer {PAGE_ACCESS_TOKEN}", "Content-Type": "application/json"}
    recipient_payload = {"comment_id": comment_id} if comment_id else {"id": sender_id}
    if link: payload = {"recipient": recipient_payload, "message": {"attachment": {"type": "template", "payload": {"template_type": "button", "text": mensagem, "buttons": [{"type": "web_url", "url": link, "title": texto_botao}]}}}}
    else: payload = {"recipient": recipient_payload, "message": {"text": mensagem}}
    requests.post(url, headers=headers, json=payload, timeout=10)
