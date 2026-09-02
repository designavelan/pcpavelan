import streamlit as st
import altair as alt
import math

def renderizar_coluna_2(ctx, ordem_elementos, get_color):
    primeiro = True
    for elemento in ordem_elementos:
        elemento = str(elemento).strip()
        
        # A Mágica do CSS no arquivo 2
        mt_class = "pull-up" if primeiro else ""
        
        if elemento == "Chão de Fábrica":
            if ctx['mapa_visual_dict']:
                html_mapa = f"<div class='{mt_class}' style='display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 20px; align-items: stretch;'>"
                
                for setor in ctx['setores_ordenados']:
                    maquinas_lista = ctx['mapa_visual_dict'][setor]
                    html_mapa += "<div style='display: flex; flex-direction: column; background: #fff; border: 1px solid #ecf0f1; border-radius: 6px; padding: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);'>"
                    html_mapa += f"<div style='background: #34495e; color: white; padding: 6px; border-radius: 4px; text-align: center; font-weight: bold; font-size: 12px; margin-bottom: 8px; text-transform: uppercase; flex-shrink: 0;'>{setor}</div>"
                    
                    html_mapa += "<div style='flex-grow: 1; margin-bottom: 10px;'>"
                    for m in sorted(maquinas_lista, key=lambda x: (x['ordem'], x['maquina'])):
                        cor_fundo = get_color(m['tipo'])
                        html_mapa += f"<div style='background: {cor_fundo}; padding: 4px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; color: white; margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center;'>"
                        html_mapa += f"<span style='white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{m['maquina_fmt']}</span><span style='opacity: 0.8; font-weight: normal; font-size: 10px; white-space:nowrap; margin-left:5px;'>{m['operadores']}</span></div>"
                    html_mapa += "</div>"
                    
                    if s_html_pecas := ctx['html_ultimas_pecas_setor'].get(setor):
                        html_mapa += "<div style='border-top: 1px dashed #bdc3c7; padding-top: 8px; flex-shrink: 0;'>"
                        html_mapa += "<div style='font-size: 10px; font-weight: bold; color: #7f8c8d; text-align: center; margin-bottom: 6px; text-transform: uppercase;'>Últimas Peças</div>"
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
                    if i < resto:
                        cards_por_linha.append(base_cards + 1)
                    else:
                        cards_por_linha.append(base_cards)
                        
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
                        
                        # Injeção Inteligente da Imagem/Ícone do Setor no Canto Superior Direito
                        icone_b64 = p.get('icone_b64')
                        if icone_b64:
                            html_cards += f"<img src='data:image/png;base64,{icone_b64}' style='position: absolute; top: 12px; right: 12px; width: 36px; height: 36px; object-fit: contain; opacity: 0.7; filter: drop-shadow(0px 2px 2px rgba(0,0,0,0.5));' />"
                        
                        html_cards += "<div>" 
                        html_cards += f"<div style='font-size:11px; font-weight:bold; opacity:0.9;'>{p.get('setor_exibicao', p['setor'])}</div>"
                        html_cards += f"<div style='font-size:18px; font-weight:900; margin-bottom:5px;'>{p['maquina_fmt']}</div>"
                        html_cards += f"<div style='font-size:11px; min-height:34px; line-height:1.2; overflow:hidden; margin-bottom:4px; display:flex; flex-direction:column; justify-content:center;'>{desc_completa}</div>"
                        html_cards += p.get('html_progresso', '')
                        html_cards += "</div>" 
                        
                        if is_fim_expediente: html_cards += f"<div style='font-size:14px; font-weight:bold; background:rgba(0,0,0,0.2); border-radius:5px; margin-top:auto; padding: 15px 0; text-transform:uppercase;'>Turno Encerrado</div>"
                        else:
                            html_cards += f"<div id='timer_{p_id}' style='font-size:24px; font-weight:bold; font-family:monospace; background:rgba(0,0,0,0.2); border-radius:5px 5px 0 0; margin-top:auto; padding: 6px 0 2px 0;'>00:00:00</div>"
                            html_cards += f"<div id='sub_timer_{p_id}' style='font-size:11px; font-style:italic; opacity:0.85; background:rgba(0,0,0,0.2); border-radius:0 0 5px 5px; padding: 0 0 6px 0; margin-top:0px;'>Calculando...</div>"
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
                
                bars_desemp = alt.Chart(ctx['df_desemp']).mark_bar(size=25).encode(
                    x=alt.X('duracao:Q', stack='zero', title='Tempo Total Utilizado', axis=alt.Axis(grid=True, labelExpr=expr_horas)),
                    y=alt.Y('maquina_exibicao:N', sort=ctx['ordem_maquinas_chart'], title=None, axis=alt.Axis(labels=False, ticks=False, domain=False)),
                    color=alt.Color('classificacao:N', scale=alt.Scale(
                        domain=['PRODUÇÃO', 'RETRABALHO', 'ROTINA', 'PARADA'],
                        range=['#27ae60', '#2ecc71', '#f39c12', '#c0392b']
                    ), legend=alt.Legend(title="", orient="top", labelFontSize=10, padding=5)),
                    order=alt.Order('ordem:Q'),
                    tooltip=[alt.Tooltip('maquina_exibicao:N', title='Máquina'), alt.Tooltip('classificacao:N', title='Categoria'), alt.Tooltip('tempo_str:N', title='Tempo'), alt.Tooltip('pct:Q', title='%', format='.1f')]
                )
                
                text_desemp = alt.Chart(ctx['df_desemp']).mark_text(align='center', baseline='middle', size=11).encode(
                    x=alt.X('midpos:Q', axis=None),
                    y=alt.Y('maquina_exibicao:N', sort=ctx['ordem_maquinas_chart'], axis=None),
                    text='label_exibicao:N',
                    color=alt.condition(alt.datum.classificacao == 'ROTINA', alt.value('#2c3e50'), alt.value('white'))
                )
                
                names_desemp = alt.Chart(ctx['df_desemp'][['maquina_exibicao', 'total_maq']].drop_duplicates()).mark_text(
                    align='left', baseline='bottom', dy=-15, size=11, fontWeight='bold', color='#34495e'
                ).encode(
                    x=alt.value(0),
                    y=alt.Y('maquina_exibicao:N', sort=ctx['ordem_maquinas_chart'], axis=None),
                    text='maquina_exibicao:N'
                )
                
                chart_desemp = alt.layer(bars_desemp, text_desemp, names_desemp).properties(height=ctx['altura_dinamica_desemp']).configure_axis(labelFontSize=10, titleFontSize=11).configure_view(strokeWidth=0)
                st.altair_chart(chart_desemp, use_container_width=True)