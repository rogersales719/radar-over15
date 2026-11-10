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

def obter_jogos_reserva(mercado="over"):
    if mercado == "over":
        return [
            {"casa": "PSV Eindhoven", "fora": "Ajax", "hora": "16:00", "pais": "Holanda", "liga": "Eredivisie", "estadio": "Philips Stadion", "odd": 1.25, "prob": 84.0, "tipo": "reserva"},
            {"casa": "Manchester City", "fora": "Tottenham", "hora": "17:30", "pais": "Inglaterra", "liga": "Premier League", "estadio": "Etihad Stadium", "odd": 1.28, "prob": 82.0, "tipo": "reserva"},
            {"casa": "Bayern München", "fora": "Bayer Leverkusen", "hora": "18:45", "pais": "Alemanha", "liga": "Bundesliga", "estadio": "Allianz Arena", "odd": 1.22, "prob": 86.0, "tipo": "reserva"},
            {"casa": "Real Madrid", "fora": "Villarreal", "hora": "20:00", "pais": "Espanha", "liga": "La Liga", "estadio": "Santiago Bernabéu", "odd": 1.30, "prob": 80.0, "tipo": "reserva"}
        ]
    else:
        return [
            {"casa": "Arsenal", "fora": "Liverpool", "hora": "16:00", "pais": "Inglaterra", "liga": "Premier League", "estadio": "Emirates Stadium", "odd": 1.68, "prob": 78.0, "tipo": "reserva"},
            {"casa": "Eintracht Frankfurt", "fora": "Borussia Dortmund", "hora": "17:30", "pais": "Alemanha", "liga": "Bundesliga", "estadio": "Deutsche Bank Park", "odd": 1.62, "prob": 81.0, "tipo": "reserva"},
            {"casa": "Atalanta", "fora": "Napoli", "hora": "19:00", "pais": "Itália", "liga": "Serie A", "estadio": "Gewiss Stadium", "odd": 1.70, "prob": 76.0, "tipo": "reserva"},
            {"casa": "Benfica", "fora": "Sporting CP", "hora": "20:30", "pais": "Portugal", "liga": "Liga Portugal", "estadio": "Estádio da Luz", "odd": 1.65, "prob": 79.0, "tipo": "reserva"}
        ]

def gerar_sistemas_apostas(top_4_jogos, prefixo="J"):
    if len(top_4_jogos) < 4:
        return {"sistema_2_4": [], "sistema_3_4": []}

    itens = []
    for i, j in enumerate(top_4_jogos):
        itens.append({
            "rotulo": f"{prefixo}{i+1}",
            "partida": f"{j['casa']} x {j['fora']}",
            "odd": j.get("odd", 1.30)
        })

    duplas = list(combinations(itens, 2))
    sistema_2_4 = []
    for combo in duplas:
        odd_total = round(combo[0]["odd"] * combo[1]["odd"], 2)
        sistema_2_4.append({
            "jogos": f"{combo[0]['partida']} + {combo[1]['partida']}",
            "rotulos": f"{combo[0]['rotulo']} + {combo[1]['rotulo']}",
            "odd_total": odd_total
        })

    triplas = list(combinations(itens, 3))
    sistema_3_4 = []
    for combo in triplas:
        odd_total = round(combo[0]["odd"] * combo[1]["odd"] * combo[2]["odd"], 2)
        sistema_3_4.append({
            "jogos": f"{combo[0]['partida']} + {combo[1]['partida']} + {combo[2]['partida']}",
            "rotulos": f"{combo[0]['rotulo']} + {combo[1]['rotulo']} + {combo[2]['rotulo']}",
            "odd_total": odd_total
        })

    return {"sistema_2_4": sistema_2_4, "sistema_3_4": sistema_3_4}

def buscar_partidas_completas(data_pesquisa):
    url = f"https://{API_HOST}/fixtures"
    params = {"date": data_pesquisa}

    candidatos_reais = []
    agora_bsb = datetime.now(FUSO_BRASILIA)
    # Jogos que começam pelo menos 45 a 60 minutos à frente para garantir folga e não descartar a tarde toda
    horario_minimo = agora_bsb + timedelta(minutes=60)

    if API_KEY and API_KEY != "SUA_CHAVE_AQUI":
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=15)
            dados = response.json().get("response", [])
            print(f"--> [DEBUG] API-Sports: {len(dados)} jogos retornados para hoje.")

            for match in dados:
                status_short = match.get("fixture", {}).get("status", {}).get("short", "")
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

                candidatos_reais.append({
                    "casa": time_casa,
                    "fora": time_fora,
                    "pais": pais,
                    "liga": liga,
                    "bandeira": bandeira,
                    "estadio": estadio,
                    "horario_brasilia": hora_bsb,
                    "datetime_bsb": dt_jogo_bsb,
                    "tipo": "real"
                })

            candidatos_reais.sort(key=lambda x: x["datetime_bsb"])
            print(f"--> [DEBUG] Jogos pré-live válidos encontrados: {len(candidatos_reais)}")

        except Exception as e:
            print(f"--> [DEBUG] Erro ao consultar API-Sports: {e}")
            candidatos_reais = []

    # Monta os 4 jogos para Over 1.5
    jogos_over = []
    if len(candidatos_reais) >= 4:
        for j in candidatos_reais[:4]:
            jogos_over.append({**j, "probabilidade": 82.0, "odd": 1.28})
    else:
        jogos_over = obter_jogos_reserva("over")

    # Monta os 4 jogos para Ambas Marcam Sim (pega os próximos da grade real)
    jogos_btts = []
    if len(candidatos_reais) >= 8:
        for j in candidatos_reais[4:8]:
            jogos_btts.append({**j, "probabilidade": 76.5, "odd": 1.65})
    elif len(candidatos_reais) >= 4:
        # Se tiver entre 4 e 7 jogos, usa os mesmos reais adaptados para o mercado de Ambas
        for j in candidatos_reais[:4]:
            jogos_btts.append({**j, "probabilidade": 74.0, "odd": 1.68})
    else:
        jogos_btts = obter_jogos_reserva("btts")

    origem = "real" if any(j.get("tipo") == "real" for j in jogos_over) else "simulado"
    return jogos_over, jogos_btts, origem

@app.route("/", methods=["GET"])
def index():
    data_hoje_bsb = obter_data_brasilia()
    jogos_over, jogos_btts, status_origem = buscar_partidas_completas(data_hoje_bsb)

    sistemas_over = gerar_sistemas_apostas(jogos_over, prefixo="OV")
    sistemas_btts = gerar_sistemas_apostas(jogos_btts, prefixo="AM")

    return render_template(
        "index.html",
        data_brasilia=data_hoje_bsb,
        jogos_over=jogos_over,
        jogos_btts=jogos_btts,
        sistemas_over=sistemas_over,
        sistemas_btts=sistemas_btts,
        origem=status_origem
    )

if __name__ == "__main__":
    app.run(debug=True, port=5000)
