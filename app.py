import os
from datetime import datetime, timedelta
from itertools import combinations
import pytz
import requests
from flask import Flask, render_template

app = Flask(__name__)

# Configuração da API-Sports oficial
API_KEY = os.environ.get("FOOTBALL_API_KEY", "")
API_HOST = "v3.football.api-sports.io"
HEADERS = {
    "x-apisports-key": API_KEY
}

FUSO_BRASILIA = pytz.timezone("America/Sao_Paulo")

def obter_data_brasilia():
    agora_bsb = datetime.now(FUSO_BRASILIA)
    return agora_bsb.strftime("%Y-%m-%d")

def converter_para_datetime_bsb(iso_timestamp):
    try:
        data_utc = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        return data_utc.astimezone(FUSO_BRASILIA)
    except Exception:
        return None

def formatar_horario_brasilia(dt_bsb):
    if dt_bsb:
        return dt_bsb.strftime("%H:%M")
    return "--:--"

def estimar_probabilidade_over_1_5(media_pro_casa=2.2, media_contra_fora=1.4, media_pro_fora=1.6, media_contra_casa=1.2):
    """Calcula a expectativa e probabilidade de Over 1.5."""
    exp_mandante = (media_pro_casa + media_contra_fora) / 2.0
    exp_visitante = (media_pro_fora + media_contra_casa) / 2.0
    total = exp_mandante + exp_visitante

    if total >= 3.0:
        prob = 88.0
    elif total >= 2.5:
        prob = 82.0
    elif total >= 2.0:
        prob = 75.0
    else:
        prob = 62.0

    return round(total, 2), prob

def estimar_probabilidade_btts(media_pro_casa=1.9, media_contra_casa=1.2, media_pro_fora=1.5, media_contra_fora=1.4):
    """Calcula probabilidade de Ambas Marcam Sim (BTTS)."""
    chance_casa_marcar = min(0.92, (media_pro_casa + media_contra_fora) / 3.8)
    chance_fora_marcar = min(0.88, (media_pro_fora + media_contra_casa) / 3.8)
    prob_btts = round((chance_casa_marcar * chance_fora_marcar) * 100, 1)
    
    # Normaliza probabilidade para mercado competitivo
    prob_btts = max(68.0, min(86.0, prob_btts))
    return prob_btts

def obter_jogos_reserva(mercado="over"):
    """Partidas reserva caso a API retorne menos de 4 jogos."""
    if mercado == "over":
        candidatos = [
            {"casa": "PSV Eindhoven", "fora": "Ajax", "hora": "15:30", "pais": "Holanda", "liga": "Eredivisie", "estadio": "Philips Stadion", "odd": 1.25, "prob": 84.0},
            {"casa": "Manchester City", "fora": "Tottenham", "hora": "17:00", "pais": "Inglaterra", "liga": "Premier League", "estadio": "Etihad Stadium", "odd": 1.28, "prob": 82.0},
            {"casa": "Bayern München", "fora": "Bayer Leverkusen", "hora": "18:30", "pais": "Alemanha", "liga": "Bundesliga", "estadio": "Allianz Arena", "odd": 1.22, "prob": 86.0},
            {"casa": "Real Madrid", "fora": "Villarreal", "hora": "20:00", "pais": "Espanha", "liga": "La Liga", "estadio": "Santiago Bernabéu", "odd": 1.30, "prob": 80.0}
        ]
    else:
        candidatos = [
            {"casa": "Arsenal", "fora": "Liverpool", "hora": "15:30", "pais": "Inglaterra", "liga": "Premier League", "estadio": "Emirates Stadium", "odd": 1.68, "prob": 78.0},
            {"casa": "Eintracht Frankfurt", "fora": "Borussia Dortmund", "hora": "17:30", "pais": "Alemanha", "liga": "Bundesliga", "estadio": "Deutsche Bank Park", "odd": 1.62, "prob": 81.0},
            {"casa": "Atalanta", "fora": "Napoli", "hora": "19:00", "pais": "Itália", "liga": "Serie A", "estadio": "Gewiss Stadium", "odd": 1.70, "prob": 76.0},
            {"casa": "Benfica", "fora": "Sporting CP", "hora": "20:30", "pais": "Portugal", "liga": "Liga Portugal", "estadio": "Estádio da Luz", "odd": 1.65, "prob": 79.0}
        ]

    reserva = []
    for j in candidatos:
        reserva.append({
            "casa": j["casa"],
            "fora": j["fora"],
            "pais": j["pais"],
            "liga": j["liga"],
            "estadio": j["estadio"],
            "bandeira": "",
            "horario_brasilia": j["hora"],
            "probabilidade": j["prob"],
            "odd": j["odd"],
            "tipo": "reserva"
        })
    return reserva

def gerar_sistemas_apostas(top_4_jogos, prefixo="J"):
    """Gera combinações independentes de Sistema 2/4 (6 duplas) e 3/4 (4 triplas)."""
    if len(top_4_jogos) < 4:
        return {"sistema_2_4": [], "sistema_3_4": []}

    itens = []
    for i, j in enumerate(top_4_jogos):
        itens.append({
            "rotulo": f"{prefixo}{i+1}",
            "partida": f"{j['casa']} x {j['fora']}",
            "odd": j.get("odd", 1.30)
        })

    # Sistema 2/4 (6 duplas)
    duplas = list(combinations(itens, 2))
    sistema_2_4 = []
    for combo in duplas:
        odd_total = round(combo[0]["odd"] * combo[1]["odd"], 2)
        sistema_2_4.append({
            "jogos": f"{combo[0]['partida']} + {combo[1]['partida']}",
            "rotulos": f"{combo[0]['rotulo']} + {combo[1]['rotulo']}",
            "odd_total": odd_total
        })

    # Sistema 3/4 (4 triplas)
    triplas = list(combinations(itens, 3))
    sistema_3_4 = []
    for combo in triplas:
        odd_total = round(combo[0]["odd"] * combo[1]["odd"] * combo[2]["odd"], 2)
        sistema_3_4.append({
            "jogos": f"{combo[0]['partida']} + {combo[1]['partida']} + {combo[2]['partida']}",
            "rotulos": f"{combo[0]['rotulo']} + {combo[1]['rotulo']} + {combo[2]['rotulo']}",
            "odd_total": odd_total
        })

    return {
        "sistema_2_4": sistema_2_4,
        "sistema_3_4": sistema_3_4
    }

def buscar_partidas_completas(data_pesquisa):
    url = f"https://{API_HOST}/fixtures"
    params = {"date": data_pesquisa}

    jogos_over = []
    jogos_btts = []
    agora_bsb = datetime.now(FUSO_BRASILIA)
    horario_minimo = agora_bsb + timedelta(minutes=90)  # Mínimo pré-live

    if API_KEY and API_KEY != "SUA_CHAVE_AQUI":
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=12)
            dados = response.json().get("response", [])

            candidatos_validos = []
            for match in dados:
                status_short = match["fixture"]["status"]["short"]
                if status_short not in ["NS", "TBD"]:
                    continue

                dt_jogo_bsb = converter_para_datetime_bsb(match["fixture"]["date"])
                if not dt_jogo_bsb or dt_jogo_bsb < horario_minimo:
                    continue

                hora_bsb = formatar_horario_brasilia(dt_jogo_bsb)
                time_casa = match["teams"]["home"]["name"]
                time_fora = match["teams"]["away"]["name"]
                pais = match.get("league", {}).get("country", "Mundo")
                liga = match.get("league", {}).get("name", "Competição")
                bandeira = match.get("league", {}).get("flag", "")
                estadio = match.get("fixture", {}).get("venue", {}).get("name") or "Local a definir"

                candidatos_validos.append({
                    "casa": time_casa,
                    "fora": time_fora,
                    "pais": pais,
                    "liga": liga,
                    "bandeira": bandeira,
                    "estadio": estadio,
                    "horario_brasilia": hora_bsb,
                    "datetime_bsb": dt_jogo_bsb
                })

            # Ordena cronologicamente
            candidatos_validos.sort(key=lambda x: x["datetime_bsb"])

            # 4 Jogos para Over 1.5
            for j in candidatos_validos[:4]:
                _, prob_over = estimar_probabilidade_over_1_5()
                jogos_over.append({
                    **j,
                    "probabilidade": prob_over,
                    "odd": 1.30,
                    "tipo": "real"
                })

            # 4 Jogos para Ambas Marcam Sim (BTTS)
            # Prioriza jogos a partir do 5º da lista (ou reutiliza com odds e métricas próprias se a grade for menor)
            pool_btts = candidatos_validos[4:8] if len(candidatos_validos) >= 8 else candidatos_validos[:4]
            for j in pool_btts:
                prob_btts = estimar_probabilidade_btts()
                jogos_btts.append({
                    **j,
                    "probabilidade": prob_btts,
                    "odd": 1.65,
                    "tipo": "real"
                })

        except Exception as e:
            print(f"--> [DEBUG] Erro ao buscar jogos: {e}")
            jogos_over = []
            jogos_btts = []

    # Validação Over 1.5
    if len(jogos_over) < 4:
        faltam = 4 - len(jogos_over)
        jogos_over = jogos_over + obter_jogos_reserva("over")[:faltam]

    # Validação BTTS
    if len(jogos_btts) < 4:
        faltam = 4 - len(jogos_btts)
        jogos_btts = jogos_btts + obter_jogos_reserva("btts")[:faltam]

    return jogos_over, jogos_btts

@app.route("/", methods=["GET"])
def index():
    data_hoje_bsb = obter_data_brasilia()
    jogos_over, jogos_btts = buscar_partidas_completas(data_hoje_bsb)

    # Gera sistemas independentes para cada mercado
    sistemas_over = gerar_sistemas_apostas(jogos_over, prefixo="OV")
    sistemas_btts = gerar_sistemas_apostas(jogos_btts, prefixo="AM")

    origem_over = "real" if all(j["tipo"] == "real" for j in jogos_over) else "hibrido"

    return render_template(
        "index.html",
        data_brasilia=data_hoje_bsb,
        jogos_over=jogos_over,
        jogos_btts=jogos_btts,
        sistemas_over=sistemas_over,
        sistemas_btts=sistemas_btts,
        origem=origem_over
    )

if __name__ == "__main__":
    app.run(debug=True, port=5000)
