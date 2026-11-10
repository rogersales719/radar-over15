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
    """Calcula a expectativa de golos e a probabilidade de Over 1.5."""
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
    """Retorna 4 partidas de demonstração caso a API não devolva jogos."""
    candidatos = [
        {"casa": "PSV Eindhoven", "fora": "Ajax", "hora": "11:30", "pro_casa": 2.6, "contra_fora": 1.3, "pro_fora": 1.7, "contra_casa": 1.2, "odd": 1.22},
        {"casa": "Manchester City", "fora": "Tottenham", "hora": "14:00", "pro_casa": 2.5, "contra_fora": 1.5, "pro_fora": 1.6, "contra_casa": 1.0, "odd": 1.28},
        {"casa": "Bayern München", "fora": "Bayer Leverkusen", "hora": "16:30", "pro_casa": 2.8, "contra_fora": 1.4, "pro_fora": 1.9, "contra_casa": 1.1, "odd": 1.25},
        {"casa": "Real Madrid", "fora": "Villarreal", "hora": "17:00", "pro_casa": 2.2, "contra_fora": 1.2, "pro_fora": 1.4, "contra_casa": 0.9, "odd": 1.30}
    ]
    analisados = []
    for j in candidatos:
        exp, prob = estimar_probabilidade_over_1_5(j["pro_casa"], j["contra_fora"], j["pro_fora"], j["contra_casa"])
        analisados.append({
            "casa": j["casa"],
            "fora": j["fora"],
            "horario_brasilia": j["hora"],
            "gols_esperados": exp,
            "probabilidade": prob,
            "odd": j["odd"]
        })
    analisados.sort(key=lambda x: x["horario_brasilia"])
    return analisados

def gerar_sistemas_apostas(top_4_jogos, odd_padrao=1.30):
    """Gera todas as combinações de Sistema 2/4 (6 duplas) e 3/4 (4 triplas)."""
    if len(top_4_jogos) < 4:
        return {"sistema_2_4": [], "sistema_3_4": []}

    itens = []
    for i, j in enumerate(top_4_jogos):
        itens.append({
            "rotulo": f"J{i+1}",
            "partida": f"{j['casa']} x {j['fora']}",
            "odd": j.get("odd", odd_pad
