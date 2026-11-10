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
    params = {"date": data_pesquisa}

    jogos_reais = []
    # Premissa: Jogos programados a partir do meio-dia (12:00) horário de Brasília
    hora_corte = 12

    if API_KEY and API_KEY != "SUA_CHAVE_AQUI":
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=15)
            dados = response.json().get("response", [])
            print(f"--> [DEBUG] Total fixtures API hoje: {len(dados)}")

            for match in dados:
                dt_bsb = converter_para_datetime_bsb(match["fixture"]["date"])
                if not dt_bsb:
                    continue

                # Filtra apenas jogos que acontecem a partir de 12:00 de Brasília
                if dt_bsb.hour < hora_corte:
                    continue

                hora_formatada = formatar_horario_brasilia(dt_bsb)
                time_casa = match["teams"]["home"]["name"]
                time_fora = match["teams"]["away"]["name"]
                pais = match.get("league", {}).get("country", "Mundo")
                liga = match.get("league", {}).get("name", "Competição")
                bandeira = match.get("league", {}).get("flag", "")
                estadio = match.get("fixture", {}).get("venue", {}).get("name") or "Local a definir"

                jogos_reais.append({
                    "casa": time_casa,
                    "fora": time_fora,
                    "pais": pais,
                    "liga": liga,
                    "bandeira": bandeira,
                    "estadio": estadio,
                    "horario_brasilia": hora_formatada,
                    "datetime_bsb": dt_bsb,
                    "tipo": "real"
                })

            # Ordena por horário crescente
            jogos_reais.sort(key=lambda x: x["datetime_bsb"])
            print(f"--> [DEBUG] Partidas a partir de 12:00 BSB: {len(jogos_reais)}")

        except Exception as e:
            print(f"--> [DEBUG] Erro API-Sports: {e}")
            jogos_reais = []

    # Separação independente dos dois mercados usando os jogos reais
    jogos_over = []
    jogos_btts = []

    if len(jogos_reais) >= 4:
        # 4 jogos para Over 1.5
        for j in jogos_reais[:4]:
            jogos_over.append({**j, "probabilidade": 82.0, "odd": 1.28})

        # 4 jogos para Ambas Marcam Sim (pega os 4 seguintes da tarde/noite)
        fonte_btts = jogos_reais[4:8] if len(jogos_reais) >= 8 else jogos_reais[:4]
        for j in fonte_btts:
            jogos_btts.append({**j, "probabilidade": 77.0, "odd": 1.65})
    else:
        # Fallback de segurança apenas se a API estiver fora do ar
        jogos_over = [
            {"casa": "Häcken W", "fora": "Chelsea W", "hora": "14:45", "pais": "World", "liga": "Champions League W", "estadio": "Arena", "odd": 1.25, "prob": 84.0, "tipo": "reserva"},
            {"casa": "Real Madrid W", "fora": "Paris FC W", "hora": "14:45", "pais": "World", "liga": "Champions League W", "estadio": "Ciudad Real Madrid", "odd": 1.28, "prob": 82.0, "tipo": "reserva"},
            {"casa": "Midtjylland W", "fora": "Odense Q W", "hora": "15:00", "pais": "Denmark", "liga": "Kvindeliga", "estadio": "Local", "odd": 1.22, "prob": 86.0, "tipo": "reserva"},
            {"casa": "Wolfsburg W", "fora": "Lyon W", "hora": "17:00", "pais": "World", "liga": "Champions League W", "estadio": "AOK Stadion", "odd": 1.30, "prob": 80.0, "tipo": "reserva"}
        ]
        jogos_btts = [
            {"casa": "Arsenal W", "fora": "Juventus W", "hora": "17:00", "pais": "World", "liga": "Champions League W", "estadio": "Emirates Stadium", "odd": 1.68, "prob": 78.0, "tipo": "reserva"},
            {"casa": "Bayern W", "fora": "Valerenga W", "hora": "17:00", "pais": "World", "liga": "Champions League W", "estadio": "FC Bayern Campus", "odd": 1.62, "prob": 81.0, "tipo": "reserva"},
            {"casa": "Barcelona W", "fora": "St. Pölten W", "hora": "17:00", "pais": "World", "liga": "Champions League W", "estadio": "Johan Cruyff", "odd": 1.70, "prob": 76.0, "tipo": "reserva"},
            {"casa": "Man City W", "fora": "Hammarby W", "hora": "17:00", "pais": "World", "liga": "Champions League W", "estadio": "Academy Stadium", "odd": 1.65, "prob": 79.0, "tipo": "reserva"}
        ]

    origem = "real" if len(jogos_reais) >= 4 else "reserva"
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
