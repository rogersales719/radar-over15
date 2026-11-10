import os
from datetime import datetime
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
    return datetime.now(FUSO_BRASILIA).strftime("%Y-%m-%d")

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

    return {"sistema_2_4": sistema_2_4, "sistema_3_4": sistema_3_4}

def buscar_partidas_do_dia(data_pesquisa):
    url = f"https://{API_HOST}/fixtures"
    # Pede à API-Sports diretamente os dados no fuso de Brasília!
    params = {
        "date": data_pesquisa,
        "timezone": "America/Sao_Paulo"
    }

    candidatos_reais = []
    agora_bsb = datetime.now(FUSO_BRASILIA)

    if API_KEY and API_KEY != "SUA_CHAVE_AQUI":
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=15)
            dados = response.json().get("response", [])
            print(f"--> [DEBUG] Total fixtures API hoje: {len(dados)}")

            for match in dados:
                fixture_info = match.get("fixture", {})
                data_str = fixture_info.get("date", "")  # Vem no fuso de SP
                
                # Extrai horário HH:MM
                try:
                    dt_jogo = datetime.fromisoformat(data_str)
                    hora_jogo = dt_jogo.hour
                    hora_formatada = dt_jogo.strftime("%H:%M")
                except Exception:
                    continue

                # Premissa: jogos a partir das 12:00 de Brasília
                if hora_jogo < 12:
                    continue

                status_short = fixture_info.get("status", {}).get("short", "")
                # Ignora apenas partidas já finalizadas ou canceladas
                if status_short in ["FT", "AET", "PEN", "CANC", "ABD", "AWD", "WO"]:
                    continue

                time_casa = match.get("teams", {}).get("home", {}).get("name", "Casa")
                time_fora = match.get("teams", {}).get("away", {}).get("name", "Fora")
                pais = match.get("league", {}).get("country", "Mundo")
                liga = match.get("league", {}).get("name", "Competição")
                bandeira = match.get("league", {}).get("flag", "")
                estadio = fixture_info.get("venue", {}).get("name") or "Local a definir"

                candidatos_reais.append({
                    "casa": time_casa,
                    "fora": time_fora,
                    "pais": pais,
                    "liga": liga,
                    "bandeira": bandeira,
                    "estadio": estadio,
                    "horario_brasilia": hora_formatada,
                    "dt_jogo": dt_jogo,
                    "tipo": "real"
                })

            # Ordena pelos horários mais próximos
            candidatos_reais.sort(key=lambda x: x["dt_jogo"])
            print(f"--> [DEBUG] Partidas válidas a partir das 12h: {len(candidatos_reais)}")

        except Exception as e:
            print(f"--> [DEBUG] Erro de conexão com API: {e}")
            candidatos_reais = []

    jogos_over = []
    jogos_btts = []

    if len(candidatos_reais) >= 4:
        # 4 Jogos reais para Over 1.5
        for j in candidatos_reais[:4]:
            jogos_over.append({**j, "probabilidade": 82.0, "odd": 1.28})

        # 4 Jogos reais para Ambas Marcam Sim (se tiver 8, pega os 4 seguintes; se tiver entre 4 e 7, usa a grade real)
        fonte_btts = candidatos_reais[4:8] if len(candidatos_reais) >= 8 else candidatos_reais[:4]
        for j in fonte_btts:
            jogos_btts.append({**j, "probabilidade": 76.5, "odd": 1.65})

        origem = "real"
    else:
        # Fallback de reserva se a API estiver indisponível
        jogos_over = [
            {"casa": "PSV Eindhoven", "fora": "Ajax", "horario_brasilia": "16:00", "pais": "Holanda", "liga": "Eredivisie", "estadio": "Philips Stadion", "odd": 1.25, "probabilidade": 84.0, "tipo": "reserva", "bandeira": ""},
            {"casa": "Manchester City", "fora": "Tottenham", "horario_brasilia": "17:30", "pais": "Inglaterra", "liga": "Premier League", "estadio": "Etihad Stadium", "odd": 1.28, "probabilidade": 82.0, "tipo": "reserva", "bandeira": ""},
            {"casa": "Bayern München", "fora": "Bayer Leverkusen", "horario_brasilia": "18:45", "pais": "Alemanha", "liga": "Bundesliga", "estadio": "Allianz Arena", "odd": 1.22, "probabilidade": 86.0, "tipo": "reserva", "bandeira": ""},
            {"casa": "Real Madrid", "fora": "Villarreal", "horario_brasilia": "20:00", "pais": "Espanha", "liga": "La Liga", "estadio": "Santiago Bernabéu", "odd": 1.30, "probabilidade": 80.0, "tipo": "reserva", "bandeira": ""}
        ]
        jogos_btts = [
            {"casa": "Arsenal", "fora": "Liverpool", "horario_brasilia": "16:00", "pais": "Inglaterra", "liga": "Premier League", "estadio": "Emirates Stadium", "odd": 1.68, "probabilidade": 78.0, "tipo": "reserva", "bandeira": ""},
            {"casa": "Eintracht Frankfurt", "fora": "Borussia Dortmund", "horario_brasilia": "17:30", "pais": "Alemanha", "liga": "Bundesliga", "estadio": "Deutsche Bank Park", "odd": 1.62, "probabilidade": 81.0, "tipo": "reserva", "bandeira": ""},
            {"casa": "Atalanta", "fora": "Napoli", "horario_brasilia": "19:00", "pais": "Itália", "liga": "Serie A", "estadio": "Gewiss Stadium", "odd": 1.70, "probabilidade": 76.0, "tipo": "reserva", "bandeira": ""},
            {"casa": "Benfica", "fora": "Sporting CP", "horario_brasilia": "20:30", "pais": "Portugal", "liga": "Liga Portugal", "estadio": "Estádio da Luz", "odd": 1.65, "probabilidade": 79.0, "tipo": "reserva", "bandeira": ""}
        ]
        origem = "simulado"

    return jogos_over, jogos_btts, origem

@app.route("/", methods=["GET"])
def index():
    data_hoje_bsb = obter_data_brasilia()
    jogos_over, jogos_btts, origem = buscar_partidas_do_dia(data_hoje_bsb)

    sistemas_over = gerar_sistemas_apostas(jogos_over, prefixo="OV")
    sistemas_btts = gerar_sistemas_apostas(jogos_btts, prefixo="AM")

    return render_template(
        "index.html",
        data_brasilia=data_hoje_bsb,
        jogos_over=jogos_over,
        jogos_btts=jogos_btts,
        sistemas_over=sistemas_over,
        sistemas_btts=sistemas_btts,
        origem=origem
    )

if __name__ == "__main__":
    app.run(debug=True, port=5000)
