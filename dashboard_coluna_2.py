import streamlit as st
import altair as alt
import math
from datetime import datetime, timedelta
import pandas as pd
import banco

def renderizar_coluna_2(ctx, ordem_elementos, get_color):
    primeiro = True
    
    agora = datetime.utcnow() - timedelta(hours=3)
    hoje_str = agora.strftime("%Y-%m-%d")
    
    # Recupera o tamanho personalizado do ícone de ocorrência
    supa = banco.conectar()
    try:
        res_mem = supa.table("memoria_sistema").select("valor").eq("chave", "tamanho_icone_oco").execute()
        altura_icone_oco = int(res_mem.data[0]['valor']) if res_mem.data else 50
    except:
        altura_icone_oco = 50
    
    for elemento in ordem_elementos:
        elemento = str(elemento).strip()
        mt_class = "pull-up" if primeiro else ""
        
        if elemento == "Chão de Fábrica":
            if ctx['mapa_visual_dict']:
                html_mapa = f"<div class='{mt_class}' style='display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 20px; align-items: stretch;'>"
                
                for setor in ctx['setores_ordenados']:
                    maquinas_lista = ctx['mapa_visual_dict'][setor]
                    html_mapa += "<div style='display: flex; flex-direction: column; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 6px; padding: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);'>"
                    html_mapa += f"<div style='background: #34495e; color: white; padding: 6px; border-radius: 4px; text-align: center; font-weight: bold; font-size: 12px; margin-bottom: 8px; text-transform: uppercase; flex-shrink: 0;'>{setor}</div>"
                    
                    html_mapa += "<div style='flex-grow: 1; margin-bottom: 10px;'>"
                    for m in sorted(maquinas_lista, key=lambda x: (x.get('ordem', 99), x.get('maquina', ''))):
                        
                        if m.get('operadores', '') == "Sem Operador":
                            cor_fundo = "var(--bg-sem-op)"
                            cor_texto = "var(--text-sem-op)"
                            borda_estilo = "1px dashed var(--border-color)"
                        else:
                            cor_fundo = get_color(m.get('tipo_registro', 'LIVRE'))
                            cor_texto = "white"
                            borda_estilo = "none"
                            
                        html_mapa += f"<div style='background: {cor_fundo}; border: {borda_estilo}; padding: 4px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; color: {cor_texto}; margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center;'>"
                        html_mapa += f"<span style='white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{m.get('maquina_fmt', '')}</span><span style='opacity: 0.8; font-weight: normal; font-size: 10px; white-space:nowrap; margin-left:5px;'>{m.get('operadores', '')}</span></div>"
                    html_mapa += "</div>"
                    
                    s_html_pecas = ctx['html_ultimas_pecas_setor'].get(setor)
                    if s_html_pecas:
                        html_mapa += "<div style='border-top: 1px dashed var(--border-color); padding-top: 8px; flex-shrink: 0;'>"
                        html_mapa += "<div style='font-size: 10px; font-weight: bold; color: var(--text-muted); text-align: center; margin-bottom: 6px; text-transform: uppercase;'>Últimas Peças</div>"
                        html_mapa += s_html_pecas
                        html_mapa += "</div>"
                        
                    html_mapa += "</div>"
                html_mapa += "</div>"
                st.markdown(html_mapa, unsafe_allow_html=True)
                primeiro = False

        elif elemento == "Cronômetros de Parada":
            if ctx['cards_exibicao']:
                total_cards = len(ctx['cards_exibicao'])
                max_row = ctx['max_cards_row']
                
                num_linhas = math.ceil(total_cards / max_row) if total_cards > 0 else 1
                base_cards = total_cards // num_linhas
                resto = total_cards % num_linhas
                
                cards_por_linha = []
                for i in range(num_linhas):
                    if i < resto: cards_por_linha.append(base_cards + 1)
                    else: cards_por_linha.append(base_cards)
                        
                idx_atual = 0
                
                for i_linha, qtd in enumerate(cards_por_linha):
                    chunk = ctx['cards_exibicao'][idx_atual : idx_atual + qtd]
                    idx_atual += qtd
                    
                    current_mt_class = mt_class if (i_linha == 0) else ""
                    html_cards = f"<div class='grid-dash {current_mt_class}'>"
                    
                    for p in chunk:
                        p_id = f"{p['setor']}_{p['maquina']}".replace(" ", "_").replace("/", "_").strip()
                        tipo_reg = p.get('tipo_registro', 'LIVRE')
                        desc_completa = p.get('descricao_completa', '')
                        is_fim_expediente = ('FIM DO EXPEDIENTE' in tipo_reg.upper() or 'FIM DO EXPEDIENTE' in desc_completa.upper())
                        cor_card = get_color(tipo_reg)
                        
                        html_cards += f"<div id='card_{p_id}' class='card-dash' style='background-color: {cor_card}; min-width: 150px;' data-tipo='{tipo_reg}'>"
                        
                        icone_setor_b64 = p.get('icone_b64')
                        icone_oco_b64 = p.get('icone_ocorrencia_b64')
                        
                        if icone_setor_b64:
                            html_cards += f"<img src='data:image/png;base64,{icone_setor_b64}' style='position: absolute; top: 12px; right: 12px; width: 36px; height: 36px; object-fit: contain; opacity: 0.7; filter: drop-shadow(0px 2px 2px rgba(0,0,0,0.5));' />"
                        
                        html_cards += "<div>" 
                        html_cards += f"<div style='font-size:11px; font-weight:bold; opacity:0.9;'>{p.get('setor_exibicao', p['setor'])}</div>"
                        html_cards += f"<div style='font-size:18px; font-weight:900; margin-bottom:5px;'>{p['maquina_fmt']}</div>"
                        html_cards += f"<div style='font-size:11px; min-height:34px; line-height:1.2; overflow:hidden; margin-bottom:4px; display:flex; flex-direction:column; justify-content:center;'>{desc_completa}</div>"
                        html_cards += p.get('html_progresso', '')
                        html_cards += "</div>" 
                        
                        html_cards += f"<div style='margin-top:auto; flex-grow: 1; display:flex; flex-direction:column; align-items:center; justify-content: flex-end; padding-top: 10px;'>"
                        
                        if icone_oco_b64:
                            html_cards += f"<div style='width: 100%; display: flex; justify-content: center; align-items: center; margin-bottom: 8px;'><img src='data:image/png;base64,{icone_oco_b64}' style='width: auto; height: {altura_icone_oco}px; object-fit: contain; opacity: 0.95; filter: drop-shadow(0px 2px 4px rgba(0,0,0,0.5));' /></div>"
                        
                        if is_fim_expediente: 
                            html_cards += f"<div style='font-size:14px; font-weight:bold; text-transform:uppercase; text-align: center; width: 100%;'>Turno Encerrado</div>"
                        else:
                            html_cards += f"<div id='timer_{p_id}' style='font-size:26px; font-weight:900; font-family:monospace; text-align: center; width: 100%; line-height: 1;'>0:00</div>"
                            html_cards += f"<div id='sub_timer_{p_id}' style='font-size:12px; font-style:italic; opacity:0.9; text-align: center; width: 100%; margin-top: 2px;'>Calculando...</div>"
                        
                        html_cards += "</div>" 
                        html_cards += "</div>" 
                    html_cards += "</div>"
                    st.markdown(html_cards, unsafe_allow_html=True)
                    
                primeiro = False

        elif elemento == "Desempenho da Fábrica":
            if not ctx['df_desemp'].empty:
                if primeiro:
                    st.markdown("<div class='pull-up'></div>", unsafe_allow_html=True)
                    primeiro = False
                    
                expr_horas = "floor(datum.value / 60) > 0 ? floor(datum.value / 60) + ':' + (datum.value % 60 < 10 ? '0' : '') + (datum.value % 60) + 'm' : (datum.value % 60) + 'm'"
                
                chart_domain = ['PRODUÇÃO', 'PASSAGEM ADICIONAL', 'RETRABALHO', 'ROTINA', 'PARADA', 'NÃO APONTADO']
                chart_range = [ctx['get_color'](t) for t in chart_domain]
                
                is_dark = ctx.get('is_dark', False)
                chart_font_color = '#ffffff' if is_dark else '#2c3e50'
                grid_color = '#333333' if is_dark else '#eeeeee'
                names_color = '#ffffff' if is_dark else '#34495e'
                
                base = alt.Chart().encode(
                    y=alt.Y('label_eixo_y:N', 
                            sort=ctx['ordem_maquinas_chart'], 
                            title=None, 
                            axis=alt.Axis(
                                labels=True,           
                                ticks=False, 
                                domain=False,
                                labelFontWeight='bold',
                                labelFontSize=12,
                                labelColor=names_color,
                                labelLimit=300,
                                labelExpr="split(datum.value, '&&')",
                                labelLineHeight=16,
                                labelPadding=10
                            )
                    )
                )
                
                bars_desemp = base.mark_bar(size=30).encode(
                    x=alt.X('duracao:Q', stack='zero', title='Tempo Total Utilizado (Geral)', axis=alt.Axis(grid=True, labelExpr=expr_horas)),
                    color=alt.Color('classificacao:N', scale=alt.Scale(domain=chart_domain, range=chart_range), legend=alt.Legend(title="", orient="top", labelFontSize=10, padding=5)),
                    order=alt.Order('ordem:Q'),
                    tooltip=[
                        alt.Tooltip('setor_fmt:N', title='Setor'), 
                        alt.Tooltip('maquina_exibicao:N', title='Máquina'), 
                        alt.Tooltip('classificacao:N', title='Categoria'), 
                        alt.Tooltip('tempo_str:N', title='Tempo'), 
                        alt.Tooltip('pct:Q', title='%', format='.1f')
                    ]
                )
                
                text_desemp = base.mark_text(align='center', baseline='middle', size=11).encode(
                    x=alt.X('midpos:Q', axis=None),
                    text='label_exibicao:N',
                    color=alt.condition(alt.datum.classificacao == 'ROTINA', alt.value('#2c3e50'), alt.value('white'))
                )
                
                # --- RECUPERANDO A VARIÁVEL DE LARGURA DO CONTEXTO ---
                layer = alt.layer(bars_desemp, text_desemp, data=ctx['df_desemp']).properties(
                    height=alt.Step(65),
                    width=ctx.get('largura_grafico', 1000) 
                )
                
                chart_desemp = layer.facet(
                    row=alt.Row('setor_fmt:N', sort=ctx['ordem_setores_chart'], title=None, header=alt.Header(
                        labelOrient='top',
                        labelAnchor='start',
                        labelAngle=0,
                        labelFontSize=13,
                        labelFontWeight='bold',
                        labelColor=names_color,
                        labelPadding=10,
                        title=None
                    )),
                    spacing=15
                ).properties(
                    background='transparent' 
                ).resolve_scale(
                    y='independent' 
                ).configure(
                    background='transparent' 
                ).configure_axis(
                    labelFontSize=10, 
                    titleFontSize=11,
                    labelColor=chart_font_color,
                    titleColor=chart_font_color,
                    gridColor=grid_color,
                    domainColor=grid_color,
                    tickColor=grid_color
                ).configure_legend(
                    labelColor=chart_font_color,
                    titleColor=chart_font_color
                ).configure_view(
                    strokeWidth=0,
                    fill='transparent' 
                )
                
                st.altair_chart(chart_desemp, use_container_width=True)