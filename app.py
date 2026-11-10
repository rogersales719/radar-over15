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
    """Retorna a data atual no horário de Brasília no formato YYYY-MM-DD."""
    agora_bsb = datetime.now(FUSO_BRASILIA)
    return agora_bsb.strftime("%Y-%m-%d")

def formatar_horario_brasilia(iso_timestamp):
    """Converte o horário UTC da partida para o horário de Brasília (HH:MM)."""
    try:
        data_utc = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        data_bsb = data_utc.astimezone(FUSO_BRASILIA)
        return data_bsb.strftime("%H:%M")
    except Exception:
        return "--:--"

def estimar_probabilidade_over_1_5(media_pro_casa, media_contra_fora, media_pro_fora, media_contra_casa):
    """Calcula a expectativa de gols e a probabilidade de Over 1.5."""
    expectativa_mandante = (media_pro_casa + media_contra_fora) / 2.0
    expectativa_visitante = (media_pro_fora + media_contra_casa) / 2.0
    total_esperado = expectativa_mandante + expectativa_visitante

    if total_esperado >= 3.0:
        probabilidade = 88.0
    elif total_esperado >= 2.5:
        probabilidade = 80.0
    elif total_esperado >= 2.0:
        probabilidade = 72.0
    else:
        probabilidade = 58.0

    return round(total_esperado, 2), probabilidade

def obter_jogos_reserva():
    """Lista de segurança para preencher partidas ausentes."""
    candidatos = [
        {"casa": "PSV Eindhoven", "fora": "Ajax", "hora": "11:30", "pro_casa": 2.6, "contra_fora": 1.3, "pro_fora": 1.7, "contra_casa": 1.2, "odd": 1.22},
        {"casa": "Manchester City", "fora": "Tottenham", "hora": "14:00", "pro_casa": 2.5, "contra_fora": 1.5, "pro_fora": 1.6, "contra_casa": 1.0, "odd": 1.28},
        {"casa": "Bayern München", "fora": "Bayer Leverkusen", "hora": "16:30", "pro_casa": 2.8, "contra_fora": 1.4, "pro_fora": 1.9, "contra_casa": 1.1, "odd": 1.25},
        {"casa": "Real Madrid", "fora": "Villarreal", "hora": "17:00", "pro_casa": 2.2, "contra_fora": 1.2, "pro_fora": 1.4, "contra_casa": 0.9, "odd": 1.30}
    ]
    reserva = []
    for j in candidatos:
        exp, prob = estimar_probabilidade_over_1_5(j["pro_casa"], j["contra_fora"], j["pro_fora"], j["contra_casa"])
        reserva.append({
            "casa": j["casa"],
            "fora": j["fora"],
            "horario_brasilia": j["hora"],
            "gols_esperados": exp,
            "probabilidade": prob,
            "odd": j["odd"],
            "tipo": "reserva"
        })
    return reserva

def gerar_sistemas_apostas(top_4_jogos, odd_padrao=1.30):
    """Gera todas as combinações de Sistema 2/4 (6 duplas) e 3/4 (4 triplas)."""
    if len(top_4_jogos) < 4:
        return {"sistema_2_4": [], "sistema_3_4": []}

    itens = []
    for i, j in enumerate(top_4_jogos):
        itens.append({
            "rotulo": f"J{i+1}",
            "partida": f"{j['casa']} x {j['fora']}",
            "odd": j.get("odd", odd_padrao)
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

def buscar_e_filtrar_jogos(data_pesquisa):
    # Endpoint correto da API-Sports oficial (sem duplicar v3)
    url = f"https://{API_HOST}/fixtures"
    params = {"date": data_pesquisa}

    jogos_reais = []

    print(f"--> [DEBUG] Buscando jogos para a data: {data_pesquisa} | API_KEY presente: {bool(API_KEY)}")

    if API_KEY and API_KEY != "SUA_CHAVE_AQUI":
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=12)
            retorno_json = response.json()
            dados = retorno_json.get("response", [])
            erros = retorno_json.get("errors", {})

            print(f"--> [DEBUG] Resposta da API: {len(dados)} jogos retornados. Erros: {erros}")

            for match in dados:
                status = match["fixture"]["status"]["short"]
                # Apenas jogos agendados ou ao vivo
                if status not in ["NS", "1H", "2H", "HT"]:
                    continue

                hora_bsb = formatar_horario_brasilia(match["fixture"]["date"])
                time_casa = match["teams"]["home"]["name"]
                time_fora = match["teams"]["away"]["name"]

                exp_gols, prob = estimar_probabilidade_over_1_5(1.9, 1.3, 1.5, 1.1)
                jogos_reais.append({
                    "casa": time_casa,
                    "fora": time_fora,
                    "horario_brasilia": hora_bsb,
                    "gols_esperados": exp_gols,
                    "probabilidade": prob,
                    "odd": 1.30,
                    "tipo": "real"
                })

                if len(jogos_reais) >= 4:
                    break
        except Exception as e:
            print(f"--> [DEBUG] Exceção ao conectar à API: {e}")
            jogos_reais = []

    total_reais = len(jogos_reais)
    if total_reais >= 4:
        resultado = jogos_reais[:4]
        status_origem = "real"
    elif total_reais > 0:
        faltam = 4 - total_reais
        reserva = obter_jogos_reserva()
        resultado = jogos_reais + reserva[:faltam]
        status_origem = f"hibrido ({total_reais} reais + {faltam} reserva)"
    else:
        resultado = obter_jogos_reserva()
        status_origem = "simulado"

    resultado.sort(key=lambda x: x["horario_brasilia"])
    return resultado, status_origem

@app.route("/", methods=["GET"])
def index():
    data_hoje_bsb = obter_data_brasilia()
    top_4, origem_dados = buscar_e_filtrar_jogos(data_hoje_bsb)
    sistemas = gerar_sistemas_apostas(top_4)

    return render_template(
        "index.html",
        data_brasilia=data_hoje_bsb,
        jogos=top_4,
        sistemas=sistemas,
        origem=origem_dados
    )

if __name__ == "__main__":
    app.run(debug=True, port=5000)
