import streamlit as st
import altair as alt
from datetime import timedelta

def renderizar_coluna_1(ctx, ordem_elementos):
    primeiro = True
    
    for elemento in ordem_elementos:
        elemento = str(elemento).strip()
        
        # O segredo: Puxa o primeiro elemento que renderizar na tela para cima agressivamente (-32px)
        mt = "-32px" if primeiro else "0px"
        
        if elemento == "Status da Produção":
            html_hero = f"""<div style="margin-top: {mt}; background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); color: white; border-radius: 10px; padding: 20px 10px; text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.2); margin-bottom: 15px;">
            <div style="font-size: 16px; text-transform: uppercase; letter-spacing: 2px; color: #bdc3c7; font-weight: 700; margin-bottom: 5px;">Status da Produção</div>
            <div style="font-size: 65px; font-weight: 900; line-height: 1; margin-bottom: 5px; color: #2ecc71;">{ctx['perc_rodando']:.0f}%</div>
            <div style="background: rgba(0,0,0,0.2); border-radius: 8px; padding: 10px; margin-top: 15px;">
            <div style="font-size: 14px; font-weight: bold; margin-bottom: 5px;">{ctx['qtd_rodando']} de {ctx['total_maq_atual']} máqs ativas</div>
            <div style="display: flex; justify-content: space-around; flex-wrap: wrap; font-size: 12px; font-weight: bold; color: #ecf0f1;">
            <span title="Produzindo">🟢 {ctx['qtd_rodando']} Prod.</span>
            <span title="Paradas">🔴 {len(ctx['maquinas_paradas_criticas'])} Par.</span>
            <span title="Pausas">🟠 {len(ctx['maquinas_pausas'])} Paus.</span>
            <span title="Aguardando">🔵 {ctx['qtd_livres']} Liv.</span>
            </div>
            </div>
            </div>"""
            st.markdown(html_hero, unsafe_allow_html=True)
            primeiro = False

        elif elemento == "Resumo de Indicadores":
            if primeiro:
                st.markdown(f"<div style='margin-top: {mt};'></div>", unsafe_allow_html=True)
                primeiro = False
                
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f"""<div style='background:#fff; padding:10px 2px; border-radius:8px; text-align:center; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); height: 65px; display:flex; flex-direction:column; justify-content:center;'>
                <div style='color:#7f8c8d; font-size: 9px; font-weight: bold; text-transform: uppercase; white-space:nowrap;'>Perdido Hoje</div>
                <div style='font-size:16px; font-weight:900; color:#c0392b; margin-top: 2px;'>{ctx['h_perdido']:02d}h{ctx['m_perdido']:02d}</div>
                </div>""", unsafe_allow_html=True)
            with c2:
                st.markdown(f"""<div style='background:#fff; padding:10px 2px; border-radius:8px; text-align:center; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); height: 65px; display:flex; flex-direction:column; justify-content:center;'>
                <div style='color:#7f8c8d; font-size: 9px; font-weight: bold; text-transform: uppercase; white-space:nowrap;'>Ofensor Atual</div>
                <div style='font-size:11px; font-weight:900; color:#e67e22; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;' title="{ctx['top_ofensor']}">{ctx['top_ofensor']}</div>
                </div>""", unsafe_allow_html=True)
            with c3:
                st.markdown(f"""<div style='background:#fff; padding:10px 2px; border-radius:8px; text-align:center; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); height: 65px; display:flex; flex-direction:column; justify-content:center;'>
                <div style='color:#7f8c8d; font-size: 9px; font-weight: bold; text-transform: uppercase; white-space:nowrap;'>Médio/Sol.</div>
                <div style='font-size:16px; font-weight:900; color:#2980b9; margin-top: 2px;'>{ctx['mttr_str']}</div>
                </div>""", unsafe_allow_html=True)
            with c4:
                st.markdown(f"""<div style='background:#fff; padding:6px 2px; border-radius:8px; text-align:center; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); height: 65px; display:flex; flex-direction:column; justify-content:center;'>
                <div style='color:#7f8c8d; font-size: 9px; font-weight: bold; text-transform: uppercase; white-space:nowrap;'>Vol. Corte (Un)</div>
                <div style='font-size:15px; font-weight:900; color:#27ae60; line-height: 1.1; margin-top: 1px;'>{ctx['vol_corte_un']}</div>
                </div>""", unsafe_allow_html=True)

        elif elemento == "Evolução (Ao Vivo)":
            if primeiro:
                st.markdown(f"<div style='margin-top: {mt};'></div>", unsafe_allow_html=True)
                primeiro = False
                
            ticks_x = []
            curr_tick = ctx['hora_inicio_turno'].replace(minute=0, second=0, microsecond=0)
            fim_arredondado = ctx['hora_fim_turno'].replace(minute=0, second=0, microsecond=0)
            if ctx['hora_fim_turno'].minute > 0: fim_arredondado += timedelta(hours=1)
            while curr_tick <= fim_arredondado:
                ticks_x.append(curr_tick.isoformat())
                curr_tick += timedelta(hours=1)
                
            chart = alt.Chart(ctx['df_plot']).mark_area(line={'color': '#2980b9'}, color='#2980b9', opacity=0.4).encode(
                x=alt.X('Hora:T', title='', scale=alt.Scale(domain=[ctx['hora_inicio_turno'].isoformat(), ctx['hora_fim_turno'].isoformat()]), axis=alt.Axis(values=ticks_x, format='%H', labelExpr="parseInt(datum.label) + 'H'", grid=True)),
                y=alt.Y('Em Operação (%):Q', title='', scale=alt.Scale(domain=[0, 100]), axis=alt.Axis(values=[0, 25, 50, 75, 100], format='.0f', grid=True)),
                tooltip=['Hora:T', 'Em Operação (%):Q']
            ).properties(height=180)
            st.altair_chart(chart, use_container_width=True)

        elif elemento == "Em Corte Agora":
            if ctx['produtos_para_exibir']:
                html_corte_agora = f"<div style='margin-top: {mt};'>"
                for p in ctx['produtos_para_exibir']:
                    is_concluido = p['perc'] >= 99.9 or p['prod'] >= p['meta']
                    cor_barra = "#27ae60" if is_concluido else "#f39c12" 
                    html_corte_agora += f"<div style='margin-bottom: 15px; background: #fff; padding: 15px; border-radius: 8px; border: 1px solid #eaeaea; box-shadow: 0 2px 5px rgba(0,0,0,0.05);'>"
                    
                    # Unificado na mesma linha conforme solicitado
                    html_corte_agora += f"<div style='font-size: 16px; font-weight: 900; color: #2c3e50; margin-bottom: 10px; line-height: 1.1; text-align: center; text-transform: uppercase;'>🪚 Cortando agora: {p['nome']}</div>"
                    
                    if is_concluido: html_corte_agora += "<div style='text-align: center; margin-bottom: 12px;'><span style='color:#27ae60; font-size:12px; font-weight:bold; background:#eafaf1; padding:4px 8px; border-radius:4px;'>✅ Lote Concluído no Corte</span></div>"
                    html_corte_agora += f"<div style='display: flex; justify-content: space-between; align-items: center; font-size: 12px; font-weight: bold; color: #7f8c8d; margin-bottom: 6px;'><span>Progresso</span><span>{p['perc']:.1f}% ({int(p['prod'])}/{int(p['meta'])})</span></div>"
                    html_corte_agora += f"<div style='width: 100%; background: #ecf0f1; height: 14px; border-radius: 7px; overflow: hidden; border: 1px solid #bdc3c7;'><div style='width: {p['perc']}%; background: {cor_barra}; height: 100%; transition: width 0.5s ease;'></div></div>"
                    html_corte_agora += "</div>"
                html_corte_agora += "</div>"
                st.markdown(html_corte_agora, unsafe_allow_html=True)
                primeiro = False

        elif elemento == "Status das OPs":
            if ctx['html_ops']:
                if primeiro:
                    st.markdown(f"<div style='margin-top: {mt};'></div>", unsafe_allow_html=True)
                    primeiro = False
                st.markdown(ctx['html_ops'], unsafe_allow_html=True)