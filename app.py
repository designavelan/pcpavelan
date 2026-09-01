import streamlit as st
# 🔒 REGRA DE SEGURANÇA: Configuração da página DEVE ser a primeira linha do Streamlit!
st.set_page_config(page_title="PCP Avelan", page_icon="🏭", layout="wide")

import streamlit.components.v1 as components
from datetime import datetime, timedelta
import banco
import configuracoes
import filtros
import disponibilidade
import ocorrencias 
import importacao
import apontamentos
import backups 
import plano_acao 
import chao_de_fabrica
import ao_vivo 
import dashboard
import desempenho
import gerenciador
import usuarios
import produtos
import caixas
import painel_ops 
import central_correcoes
import assistente_ia
import analise  
import capacidade_produtiva
from streamlit_option_menu import option_menu
import base64

# ==========================================
# 🕵️ IDENTIFICADOR DE AMBIENTE DEV (LOCALHOST)
# ==========================================
is_local_dev = False
host = ""
try: 
    host = st.context.headers.get("Host", "")
except:
    try:
        from streamlit.web.server.websocket_headers import _get_websocket_headers
        host = _get_websocket_headers().get("Host", "")
    except: pass
    
if host and ("localhost" in host.lower() or "127.0.0.1" in host):
    is_local_dev = True

# ==========================================
# MOTOR DE HEARTBEAT (MONITORAMENTO SILENCIOSO)
# ==========================================
def registrar_heartbeat():
    """Registra a atividade do usuário a cada 5 minutos no banco de dados."""
    usuario_logado = st.session_state.get('usuario_logado')
    if not usuario_logado:
        return

    nome_usuario = usuario_logado.get('nome', 'Desconhecido')
    username = usuario_logado.get('username', '').strip().lower()

    if nome_usuario == "Admin Master" or username == "admin":
        return

    aba_atual = st.session_state.get('aba_atual', 'Desconhecida')
    agora = datetime.utcnow() - timedelta(hours=3)

    if 'sessao_db_id' not in st.session_state:
        st.session_state['sessao_db_id'] = None
    if 'ultimo_ping' not in st.session_state:
        st.session_state['ultimo_ping'] = None

    ultimo_ping = st.session_state['ultimo_ping']

    if ultimo_ping is None or (agora - ultimo_ping).total_seconds() > 300:
        agora_str = agora.strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            supa = banco.conectar()
            
            if st.session_state['sessao_db_id'] is None:
                dados = {
                    "usuario": nome_usuario,
                    "inicio": agora_str,
                    "ultima_atividade": agora_str,
                    "ultima_aba": aba_atual
                }
                resp = supa.table("registro_sessoes").insert([dados]).execute()
                if resp.data:
                    st.session_state['sessao_db_id'] = resp.data[0]['id']
                    st.session_state['ultimo_ping'] = agora
            else:
                dados = {
                    "ultima_atividade": agora_str,
                    "ultima_aba": aba_atual
                }
                supa.table("registro_sessoes").update(dados).eq("id", st.session_state['sessao_db_id']).execute()
                st.session_state['ultimo_ping'] = agora
                
        except Exception as e:
            pass 

# Carrega configurações visuais
try:
    cfg = banco.obter_configuracoes()
    titulo_app = cfg.get('titulo_programa', 'PCP Avelan')
    modo_manutencao = cfg.get('modo_manutencao', False)
    previsao_retorno = cfg.get('previsao_retorno', 'Em breve')
except:
    cfg = {}
    titulo_app = 'PCP Avelan'
    modo_manutencao = False
    previsao_retorno = ''

# ==========================================
# 1. SISTEMA DE LOGIN COM PERSISTÊNCIA E MANUTENÇÃO
# ==========================================
if 'usuario_logado' not in st.session_state:
    st.session_state['usuario_logado'] = None

if 'logout_explicito' not in st.session_state:
    st.session_state['logout_explicito'] = False

# 🚀 MÁGICA DO AUTO-LOGIN PARA O DESENVOLVEDOR 
if st.session_state['usuario_logado'] is None and not st.session_state['logout_explicito']:
    if is_local_dev:
        user_admin = banco.obter_usuario_por_login("admin")
        if user_admin:
            st.session_state['usuario_logado'] = user_admin
            st.rerun()

if st.session_state['usuario_logado'] is None:
    try:
        if hasattr(st, 'query_params') and 'session' in st.query_params:
            decoded_user = base64.b64decode(st.query_params['session']).decode('utf-8')
            user_valido = banco.obter_usuario_por_login(decoded_user)
            if user_valido:
                st.session_state['usuario_logado'] = user_valido
        elif hasattr(st, 'experimental_get_query_params'):
            params = st.experimental_get_query_params()
            if 'session' in params:
                decoded_user = base64.b64decode(params['session'][0]).decode('utf-8')
                user_valido = banco.obter_usuario_por_login(decoded_user)
                if user_valido:
                    st.session_state['usuario_logado'] = user_valido
    except:
        pass

if st.session_state['usuario_logado'] is None:
    st.markdown("""
        <style>
        header[data-testid="stHeader"] { display: none !important; }
        .block-container { max-width: 450px !important; padding-top: 5rem !important; }
        </style>
    """, unsafe_allow_html=True)
    
    logo_b64 = cfg.get('logo_base64', None)
    if logo_b64:
        st.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{logo_b64}" style="max-height: 80px; margin-bottom: 20px;"></div>', unsafe_allow_html=True)
    
    st.markdown(f"<h2 style='text-align: center; color: #2c3e50;'>🏭 {titulo_app}</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #7f8c8d; margin-bottom: 30px;'>Acesso Restrito</p>", unsafe_allow_html=True)
    
    with st.form("form_login"):
        login = st.text_input("Usuário", placeholder="Digite seu login")
        senha = st.text_input("Senha", type="password", placeholder="Digite sua senha")
        submit = st.form_submit_button("Entrar no Sistema", use_container_width=True, type="primary")
        
        if submit:
            if not login.strip() and senha:
                login = "admin"
                
            if login and senha:
                if modo_manutencao and login.strip().lower() != "admin":
                    st.error("🚧 Acesso negado: O sistema encontra-se em manutenção.")
                else:
                    user_valido = banco.autenticar_usuario(login, senha)
                    if user_valido:
                        st.session_state['usuario_logado'] = user_valido
                        st.session_state['logout_explicito'] = False 
                        encoded_user = base64.b64encode(user_valido['username'].encode('utf-8')).decode('utf-8')
                        try: st.query_params['session'] = encoded_user
                        except: st.experimental_set_query_params(session=encoded_user)
                        st.rerun()
                    else:
                        st.error("❌ Usuário ou senha incorretos, ou conta desativada.")
            else:
                st.warning("⚠️ Preencha usuário e senha.")
                
    if modo_manutencao:
        st.markdown(f"""
        <div style="background-color: #fdf3f2; border-left: 5px solid #e74c3c; padding: 15px; margin-top: 25px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
            <h4 style="color: #c0392b; margin: 0 0 5px 0; font-size: 16px;">🚧 SISTEMA EM MANUTENÇÃO</h4>
            <p style="color: #e74c3c; margin: 0; font-size: 14px; line-height: 1.4;">Estou realizando algumas atualizações no sistema no momento. Por favor, aguarde a liberação!<br><br><b>⏳ Previsão de retorno:</b> {previsao_retorno}</p>
        </div>
        """, unsafe_allow_html=True)
        
    st.stop() 

# ==========================================
# 2. LÓGICA DE PERMISSÃO E IDENTIFICAÇÃO DE ABA 
# ==========================================
usuario_atual = st.session_state['usuario_logado']

if modo_manutencao and usuario_atual.get('username', '').lower() != "admin":
    st.session_state.clear()
    st.session_state['usuario_logado'] = None
    st.session_state['logout_explicito'] = True
    try: st.query_params.clear()
    except: st.experimental_set_query_params()
    st.rerun()

perfil_atual = usuario_atual.get('perfis_acesso', {})
is_admin = perfil_atual.get('is_admin', False)
abas_permitidas_str = perfil_atual.get('abas_permitidas', '')

try:
    if hasattr(st, 'query_params') and 'codigo_alvo' in st.query_params:
        st.session_state['codigo_alvo'] = st.query_params['codigo_alvo']
        st.session_state['aba_atual'] = "🔎 Ocorrências"
        filtros.salvar_memoria() 
        st.query_params.clear()
        try: st.query_params['session'] = base64.b64encode(usuario_atual['username'].encode('utf-8')).decode('utf-8')
        except: pass
    elif hasattr(st, 'experimental_get_query_params') and 'codigo_alvo' in st.experimental_get_query_params():
        st.session_state['codigo_alvo'] = st.experimental_get_query_params()['codigo_alvo'][0]
        st.session_state['aba_atual'] = "🔎 Ocorrências"
        filtros.salvar_memoria()
        st.experimental_set_query_params(session=base64.b64encode(usuario_atual['username'].encode('utf-8')).decode('utf-8'))
except: pass

st.markdown("""
    <style>
    header[data-testid="stHeader"] { display: none !important; }
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; max-width: 100% !important; }
    .cabecalho-responsivo { display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px; }
    .logo-container { display: flex; align-items: center; gap: 20px; }
    .logo-responsiva { max-height: 60px; object-fit: contain; }
    .titulo-responsivo { margin: 0; padding: 0; font-size: 2.5rem; }
    ul.nav-pills { flex-wrap: nowrap !important; overflow-x: auto !important; overflow-y: hidden !important; scrollbar-width: none !important; }
    ul.nav-pills::-webkit-scrollbar { display: none !important; }
    li.nav-item { white-space: nowrap !important; }
    @media (max-width: 768px) {
        .cabecalho-responsivo { flex-direction: column; justify-content: center; text-align: center; gap: 10px; margin-top: 10px; }
        .logo-responsiva { max-height: 80px; } .titulo-responsivo { font-size: 2rem; }
    }
    </style>
""", unsafe_allow_html=True)

df_nuvem = banco.obter_dados_nuvem()
df_codigos = banco.obter_codigos()
meta, jornada, m_das, m_as, t_das, t_as = configuracoes.obter_parametros()

todas_abas_padrao = ["📱 Chão de Fábrica", "🔴 Ao Vivo", "📺 Dashboard", "🎯 Painel de OPs", "🏆 Desempenho", "💡 Plano de Ação", "📈 Disponibilidade", "📋 Apontamentos", "🔎 Ocorrências", "📊 Análise", "⚡ Capacidade Produtiva", "🤖 Pergunte para a IA", "📦 Produtos", "📦 Caixas", "⚙️ Configurações", "👥 Controle de Acessos"]

if is_admin or abas_permitidas_str.upper() == 'TODAS': abas_usuario = todas_abas_padrao.copy()
else:
    abas_usuario = [aba for aba in todas_abas_padrao if aba in abas_permitidas_str]
    if not abas_usuario: abas_usuario = ["📱 Chão de Fábrica"]

ordem_str = cfg.get('ordem_abas', None)
if ordem_str:
    todas_abas = [a.strip() for a in ordem_str.split(',') if a.strip() in abas_usuario]
    for a in abas_usuario:
        if a not in todas_abas: todas_abas.append(a)
else: todas_abas = abas_usuario.copy()

aba_padrao_salva = cfg.get('aba_padrao', todas_abas[0])
if aba_padrao_salva not in todas_abas: aba_padrao_salva = todas_abas[0]

lembrar_aba_ligado = cfg.get('lembrar_aba', True)

if 'aba_atual' not in st.session_state:
    if lembrar_aba_ligado:
        memoria = filtros.carregar_memoria()
        aba_cache = memoria.get("aba_atual", "")
        st.session_state.aba_atual = aba_cache if aba_cache in todas_abas else aba_padrao_salva
    else: st.session_state.aba_atual = aba_padrao_salva

if st.session_state.aba_atual not in todas_abas: st.session_state.aba_atual = todas_abas[0]

# ==========================================
# 3. CABEÇALHO GLOBAL CONDICIONAL
# ==========================================
if st.session_state.aba_atual != "📱 Chão de Fábrica" and st.session_state.aba_atual != "📺 Dashboard":
    c1, c2 = st.columns([8, 2.5]) 
    with c1:
        logo_b64 = cfg.get('logo_base64', None)
        if logo_b64:
            st.markdown(f'<div class="logo-container"><img src="data:image/png;base64,{logo_b64}" class="logo-responsiva"><h1 class="titulo-responsivo">{titulo_app}</h1></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="logo-container"><h1 class="titulo-responsivo">🏭 {titulo_app}</h1></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div style='text-align: right; color: #7f8c8d; font-size: 14px; margin-top: 5px; margin-bottom: 8px;'>👤 Olá, <b>{usuario_atual['nome']}</b></div>", unsafe_allow_html=True)
        
        if is_local_dev:
            col_sino, col_trocar, col_sair = st.columns([2.5, 4.5, 3])
        else:
            col_sino, col_sair = st.columns([3, 7])

        with col_sino:
            tem_acesso_correcoes = is_admin or "🔔 Central de Correções" in abas_permitidas_str
            if tem_acesso_correcoes:
                pendentes = banco.obter_solicitacoes_pendentes()
                qtd_pendentes = len(pendentes) if pendentes else 0
                tipo_botao = "primary" if qtd_pendentes > 0 else "secondary"
                if st.button(f"🔔 {qtd_pendentes}", key="btn_sino_correcoes", help="Central de Correções", type=tipo_botao, use_container_width=True):
                    central_correcoes.abrir_janela(usuario_atual['nome'])

        # BOTÃO EXCLUSIVO PARA O DESENVOLVEDOR (Troca sem Senha)
        if is_local_dev:
            with col_trocar:
                with st.popover("🔄 Trocar", use_container_width=True):
                    st.markdown("<div style='font-size: 13px; font-weight: bold; margin-bottom: 10px; color: #e67e22;'>🛠️ DEV: Troca Rápida</div>", unsafe_allow_html=True)
                    
                    def efetuar_troca(u_novo):
                        st.session_state.clear()
                        
                        st.session_state['usuario_logado'] = u_novo
                        st.session_state['logout_explicito'] = False
                        
                        encoded = base64.b64encode(u_novo['username'].encode('utf-8')).decode('utf-8')
                        try: st.query_params['session'] = encoded
                        except: 
                            try: st.experimental_set_query_params(session=encoded)
                            except: pass

                    lista_usuarios = []
                    try:
                        supa = banco.conectar()
                        resp_u = supa.table('usuarios').select('*, perfis_acesso(*)').eq('ativo', True).order('nome').execute()
                        if resp_u.data:
                            lista_usuarios = resp_u.data
                    except Exception as e:
                        st.write("Erro ao carregar usuários do banco.")
                    
                    for u_data in lista_usuarios:
                        if str(u_data.get('username')).strip().lower() != str(usuario_atual.get('username')).strip().lower():
                            st.button(f"{u_data['nome']}", key=f"dev_swap_{u_data['username']}", on_click=efetuar_troca, args=(u_data,), use_container_width=True)

        with col_sair:
            if st.button("🚪 Sair", use_container_width=True):
                st.session_state.clear() 
                st.session_state['usuario_logado'] = None
                st.session_state['logout_explicito'] = True 
                try: st.query_params.clear()
                except: st.experimental_set_query_params()
                st.rerun()

    if modo_manutencao:
        st.markdown("""<div style='background-color:#e74c3c; color:white; padding:8px 15px; border-radius:5px; text-align:center; font-weight:bold; margin-top:10px; margin-bottom:10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>⚠️ ATENÇÃO: O MODO MANUTENÇÃO ESTÁ ATIVADO. OPERADORES ESTÃO BLOQUEADOS.</div>""", unsafe_allow_html=True)

    st.markdown("<hr style='margin-top: 5px; margin-bottom: 10px; opacity: 0.2;'>", unsafe_allow_html=True)

# ==========================================
# 4. APLICAÇÃO E ROTEAMENTO
# ==========================================
if st.session_state.aba_atual not in ["📱 Chão de Fábrica", "🔴 Ao Vivo", "📺 Dashboard", "🎯 Painel de OPs", "🏆 Desempenho", "⚙️ Configurações", "👥 Controle de Acessos", "📦 Produtos", "📦 Caixas", "🤖 Pergunte para a IA", "⚡ Capacidade Produtiva"]:
    filtros.renderizar_barra_superior(df_nuvem)
    filtros_selecionados = filtros.obter_filtros_atuais()
    st.markdown("<hr style='margin-top: 10px; margin-bottom: 20px; opacity: 0.2;'>", unsafe_allow_html=True)
else:
    filtros_selecionados = filtros.obter_filtros_atuais()
    if st.session_state.aba_atual == "🔴 Ao Vivo":
        st.markdown(f"<div style='text-align:right; margin-bottom:15px;'><span style='background:#f1f1f1; padding:5px 15px; border-radius:5px;'>Filtro Atual: <b>{filtros_selecionados['setor']}</b></span></div>", unsafe_allow_html=True)

idx_atual = todas_abas.index(st.session_state.aba_atual)

if len(todas_abas) > 1 and st.session_state.aba_atual != "📺 Dashboard":
    escolha = option_menu(
        menu_title=None,
        options=todas_abas,
        default_index=idx_atual,
        orientation="horizontal",
        icons=[''] * len(todas_abas), 
        styles={
            "container": {"padding": "0!important", "background-color": "#f8f9fa", "border-radius": "5px", "margin-bottom": "25px"},
            "icon": {"display": "none"},
            "nav-link": {"font-size": "15px", "text-align": "center", "margin": "0px 5px", "white-space": "nowrap", "--hover-color": "#eee"},
            "nav-link-selected": {"background-color": "#2980b9"},
        }
    )
elif st.session_state.aba_atual == "📺 Dashboard":
    escolha = "📺 Dashboard"
else:
    escolha = todas_abas[0]

if escolha != st.session_state.aba_atual:
    st.session_state.aba_atual = escolha
    filtros.salvar_memoria() 
    st.rerun()

registrar_heartbeat()

# ROTEADOR DE ABAS
if st.session_state.aba_atual == "📱 Chão de Fábrica": chao_de_fabrica.renderizar(df_nuvem, df_codigos)
elif st.session_state.aba_atual == "🔴 Ao Vivo": ao_vivo.renderizar(df_nuvem, df_codigos, filtros_selecionados)
elif st.session_state.aba_atual == "📺 Dashboard": dashboard.renderizar(df_nuvem, df_codigos, filtros_selecionados)
elif st.session_state.aba_atual == "🎯 Painel de OPs": painel_ops.renderizar()
elif st.session_state.aba_atual == "🏆 Desempenho": desempenho.renderizar()
elif st.session_state.aba_atual == "💡 Plano de Ação": 
    if not df_nuvem.empty: plano_acao.renderizar(df_nuvem, df_codigos, filtros_selecionados, jornada)
    else: st.info("O banco de dados está vazio.")
elif st.session_state.aba_atual == "📈 Disponibilidade":
    if not df_nuvem.empty: disponibilidade.renderizar(df_nuvem, df_codigos, filtros_selecionados, jornada, meta)
    else: st.info("O banco de dados está vazio.")
elif st.session_state.aba_atual == "🔎 Ocorrências":
    if not df_nuvem.empty: ocorrencias.renderizar(df_nuvem, df_codigos, filtros_selecionados)
    else: st.info("O banco de dados está vazio.")
elif st.session_state.aba_atual == "📋 Apontamentos":
    if not df_nuvem.empty: apontamentos.renderizar(df_nuvem, df_codigos, filtros_selecionados)
    else: st.info("O banco de dados está vazio.")
elif st.session_state.aba_atual == "📊 Análise":
    if not df_nuvem.empty: analise.renderizar(df_nuvem, df_codigos, filtros_selecionados)
    else: st.info("O banco de dados está vazio.")
elif st.session_state.aba_atual == "⚡ Capacidade Produtiva":
    if not df_nuvem.empty: capacidade_produtiva.renderizar(df_nuvem, df_codigos, filtros_selecionados)
    else: st.info("O banco de dados está vazio.")
elif st.session_state.aba_atual == "👥 Controle de Acessos":
    usuarios.renderizar(df_nuvem)
elif st.session_state.aba_atual == "📦 Produtos":
    produtos.renderizar()
elif st.session_state.aba_atual == "📦 Caixas": 
    caixas.renderizar()
elif st.session_state.aba_atual == "🤖 Pergunte para a IA":
    assistente_ia.renderizar()
elif st.session_state.aba_atual == "⚙️ Configurações":
    aba_interna, aba_config_abas, aba_estrutura, aba_produtos_linha, aba_importacoes, aba_cores, aba_backup, aba_gerenciador, aba_acessos, aba_auditoria = st.tabs(["⚙️ Ajustes Gerais", "📑 Config. de Abas", "🏭 Estrutura", "🟢 Produtos em Linha", "📥 Importação", "🎨 Cores", "💾 Backup", "🛠️ Gerenciador de Dados", "📡 Registro de Acessos", "🔎 Auditoria de Chão de Fábrica"])
    
    with aba_interna: configuracoes.renderizar()
    with aba_config_abas: configuracoes.renderizar_config_abas()
    with aba_estrutura: configuracoes.renderizar_estrutura()
    with aba_produtos_linha: configuracoes.renderizar_produtos_linha()
    with aba_importacoes:
        importacao.renderizar_producao()
        st.markdown("<br>", unsafe_allow_html=True)
        importacao.renderizar_codigos()
    with aba_cores: configuracoes.renderizar_cores()
    with aba_backup: backups.renderizar()
    with aba_gerenciador: gerenciador.renderizar(df_nuvem)
    with aba_acessos: configuracoes.renderizar_registro_acessos()
    with aba_auditoria: configuracoes.renderizar_auditoria()

# BOTÕES DE CONTROLE DO MODO TV
if st.session_state.aba_atual == "📺 Dashboard":
    st.markdown("<br>", unsafe_allow_html=True)
    c_btn1, c_btn2, c_btn3 = st.columns([7, 1.5, 1.5])
    with c_btn2:
        if st.button("🔄 Atualizar", use_container_width=True, type="primary"):
            st.rerun()
    with c_btn3:
        if st.button("⬅️ Sair do Modo TV", use_container_width=True):
            st.session_state.aba_atual = todas_abas[0] if todas_abas else "🔴 Ao Vivo"
            st.rerun()