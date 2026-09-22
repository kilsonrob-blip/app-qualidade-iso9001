import os
import hashlib
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Integer, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# --- CONFIGURAÇÃO DO BANCO DE DADOS (SQLAlchemy) ---
Base = declarative_base()

class NaoConformidadeModel(Base):
    __tablename__ = 'nao_conformidades'
    id_nc = Column(String, primary_key=True)
    data_identificacao = Column(DateTime, default=datetime.utcnow)
    descricao_saida = Column(Text, nullable=False)
    processo_origem = Column(String, nullable=False)
    responsavel_identificacao = Column(String, nullable=False)
    impacto_potencial = Column(String, nullable=False)
    status = Column(String, default="Identificado/Segregado")
    tratativa_adotada = Column(String, nullable=True)
    detalhes_tratativa = Column(Text, nullable=True)
    caminho_evidencia = Column(String, nullable=True)
    prazo_sla = Column(DateTime, nullable=False)
    
    # Campos da Causa Raiz (5 Porquês)
    porque_1 = Column(Text, nullable=True)
    porque_2 = Column(Text, nullable=True)
    porque_3 = Column(Text, nullable=True)
    porque_4 = Column(Text, nullable=True)
    porque_5 = Column(Text, nullable=True)
    causa_raiz_definida = Column(Text, nullable=True)
    
    autorizado_por = Column(String, nullable=True)
    data_fechamento = Column(DateTime, nullable=True)
    informacao_documentada_retida = Column(Boolean, default=False)

class AcoesPreventivasModel(Base):
    __tablename__ = 'acoes_preventivas'
    id_ap = Column(String, primary_key=True)
    data_abertura = Column(DateTime, default=datetime.utcnow)
    processo = Column(String, nullable=False)
    causa_raiz_gatilho = Column(Text, nullable=False)
    descricao_plano = Column(Text, nullable=False)
    status = Column(String, default="Aberta")

# Inicialização do Banco SQLite
engine = create_engine("sqlite:///iso9001_qualidade_v2.db", echo=False)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# --- USUÁRIOS E SEGURANÇA (SHA-256) ---
USUARIOS = {
    "operador": {"senha": hashlib.sha256("senha123".encode()).hexdigest(), "perfil": "Operador"},
    "gerente": {"senha": hashlib.sha256("senha123".encode()).hexdigest(), "perfil": "Gerente"},
    "auditor": {"senha": hashlib.sha256("senha123".encode()).hexdigest(), "perfil": "Auditor"}
}

def autenticar(usuario, senha):
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()
    if usuario in USUARIOS and USUARIOS[usuario]["senha"] == senha_hash:
        return USUARIOS[usuario]["perfil"]
    return None

# --- LÓGICA DE NEGÓCIO / GATILHOS DA QUALIDADE ---
def verificar_reincidencia_e_gerar_ap(session, processo, causa_raiz):
    count = session.query(NaoConformidadeModel).filter(
        NaoConformidadeModel.processo_origem == processo,
        NaoConformidadeModel.causa_raiz_definida == causa_raiz,
        NaoConformidadeModel.status == "Concluído"
    ).count()
    
    if count >= 3:
        id_ap_count = session.query(AcoesPreventivasModel).count()
        id_ap = f"AP-{datetime.now().strftime('%Y')}-{(id_ap_count + 1):04d}"
        
        ap_existente = session.query(AcoesPreventivasModel).filter_by(processo=processo, causa_raiz_gatilho=causa_raiz).first()
        if not ap_existente:
            nova_ap = AcoesPreventivasModel(
                id_ap=id_ap,
                processo=processo,
                causa_raiz_gatilho=causa_raiz,
                descricao_plano=f"Plano de Ação Corretiva/Preventiva Global gerado automaticamente devido a {count} reincidências de falhas no setor."
            )
            session.add(nova_ap)
            session.commit()
            return id_ap
    return None

# --- INTERFACE WEB STREAMLIT ---
st.set_page_config(page_title="SGQ ISO 9001", layout="wide")

if "perfil" not in st.session_state:
    st.session_state["perfil"] = None
    st.session_state["usuario"] = None

if st.session_state["perfil"] is None:
    st.title("🔐 Sistema de Gestão da Qualidade - Login")
    user_input = st.text_input("Usuário")
    pass_input = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        perfil = autenticar(user_input, pass_input)
        if perfil:
            st.session_state["perfil"] = perfil
            st.session_state["usuario"] = user_input
            st.rerun()
        else:
            st.error("Credenciais inválidas.")
else:
    # Sidebar de Navegação
    st.sidebar.title(f"👤 {st.session_state['usuario'].upper()}")
    st.sidebar.write(f"Perfil: **{st.session_state['perfil']}**")
    menu = st.sidebar.radio("Navegação", ["Dashboard", "Registrar Saída NC", "Tratativa & Evidências", "Causa Raiz & Fechamento", "Planos Preventivos", "Auditoria de Dados"])
    
    if st.sidebar.button("Sair"):
        st.session_state["perfil"] = None
        st.session_state["usuario"] = None
        st.rerun()

    session = Session()

    # --- MÓDULO 1: DASHBOARD ---
    if menu == "Dashboard":
        st.title("📊 Painel de Controle de Saídas Não Conformes")
        
        ncs = session.query(NaoConformidadeModel).all()
        df = pd.DataFrame([nc.__dict__ for nc in ncs]) if ncs else pd.DataFrame()
        
        if not df.empty:
            df['atrasada'] = df.apply(lambda r: r['status'] != "Concluído" and datetime.utcnow() > r['prazo_sla'], axis=1)
            total_ncs = len(df)
            atrasadas = df['atrasada'].sum()
            aps_ativas = session.query(AcoesPreventivasModel).count()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Total de Não Conformidades", total_ncs)
            c2.metric("Ocorrências com SLA Atrasado", atrasadas, delta_color="inverse")
            c3.metric("Planos Preventivos Globais", aps_ativas)
            
            # Gráficos
            fig, axes = plt.subplots(1, 2, figsize=(14, 5))
            sns.set_theme(style="whitegrid")
            
            # Pizza por Processo
            df['processo_origem'].value_counts().plot(kind='pie', ax=axes[0], autopct='%1.1f%%', colors=sns.color_palette("Blues_r"))
            axes[0].set_title("Ocorrências por Setor")
            axes[0].set_ylabel("")
            
            # Barras por Impacto
            sns.countplot(data=df, x='impacto_potencial', hue='status', ax=axes[1], palette="Set2")
            axes[1].set_title("Status por Severidade de Impacto")
            
            st.pyplot(fig)
        else:
            st.info("Nenhuma ocorrência registrada para gerar gráficos estruturados.")

    # --- MÓDULO 2: CADASTRO ---
    elif menu == "Registrar Saída NC":
        st.title("📝 Nova Saída Não Conforme (Cláusula 8.7.1)")
        
        desc = st.text_area("Descrição detalhada do desvio ou saída não conforme")
        processo = st.selectbox("Processo / Setor de Origem", ["Produção", "Logística", "Engenharia", "Suprimentos", "Qualidade"])
        impacto = st.selectbox("Impacto Potencial de Risco", ["Baixo", "Médio", "Alto"])
        
        if st.button("Salvar Registro"):
            if desc:
                id_count = session.query(NaoConformidadeModel).count()
                id_nc = f"NC-{datetime.now().strftime('%Y')}-{(id_count + 1):04d}"
                
                nova_nc = NaoConformidadeModel(
                    id_nc=id_nc,
                    descricao_saida=desc,
                    processo_origem=processo,
                    responsavel_identificacao=st.session_state["usuario"],
                    impacto_potencial=impacto,
                    prazo_sla=datetime.utcnow() + timedelta(days=15)
                )
                session.add(nova_nc)
                session.commit()
                st.success(f"Ocorrência {id_nc} registrada com sucesso! SLA definido para 15 dias.")
            else:
                st.error("Por favor, preencha a descrição do desvio.")

       # --- MÓDULO 3: TRATATIVA & EVIDÊNCIAS ---
    elif menu == "Tratativa & Evidências":
        st.title("🛠️ Disposição e Ações de Contenção (Cláusula 8.7)")
        
        # Filtrar apenas as NCs que aguardam tratativa
        ncs_abertas = session.query(NaoConformidadeModel).filter(NaoConformidadeModel.status == "Identificado/Segregado").all()
        
        if not ncs_abertas:
            st.success("Não existem novas saídas não conformes aguardando disposição inicial.")
        else:
            lista_ncs = [f"{nc.id_nc} - {nc.processo_origem}: {nc.descricao_saida[:40]}..." for nc in ncs_abertas]
            nc_selecionada = st.selectbox("Selecione a NC para aplicar Tratativa/Contenção", lista_ncs)
            
            # CORREÇÃO AQUI: Pegar o índice [0] para obter apenas a String do ID (ex: "NC-2026-0001")
            id_nc_atual = nc_selecionada.split(" - ")[0]
            
            nc_obj = session.query(NaoConformidadeModel).filter_by(id_nc=id_nc_atual).first()
            
            if nc_obj:
                st.warning(f"**Descrição Completa do Desvio:** {nc_obj.descricao_saida}")
                
                # Formulário de Tratativa
                tratativa = st.selectbox("Ação de Disposição Imediata", ["Correção", "Segregação/Retenção", "Devolução", "Suspensão de Provisão de Produtos/Serviços"])
                detalhes = st.text_area("Detalhamento da Ação de Contenção Executada")
                evidencia = st.text_input("Link/Caminho da Evidência Digital (Informação Documentada Retida)")
                
                if st.button("Gravar Tratativa"):
                    if detalhes:
                        nc_obj.tratativa_adotada = tratativa
                        nc_obj.detalhes_tratativa = detalhes
                        nc_obj.caminho_evidencia = evidencia
                        nc_obj.status = "Em Análise de Causa"
                        session.commit()
                        st.success(f"Tratativa registrada para {id_nc_atual}! O desvio seguiu para análise de causa raiz.")
                        st.rerun()
                    else:
                        st.error("Descreva os detalhes da ação executada.")
            else:
                st.error("Erro ao carregar os dados desta Não Conformidade.")

    # --- MÓDULO 4: CAUSA RAIZ & FECHAMENTO ---
    elif menu == "Causa Raiz & Fechamento":
        st.title("🔍 Análise de Causa Raiz & Encerramento (Cláusula 10.2)")
        
        ncs_para_causa = session.query(NaoConformidadeModel).filter(NaoConformidadeModel.status == "Em Análise de Causa").all()
        
        if not ncs_para_causa:
            st.info("Nenhuma não conformidade aguardando análise de causa raiz profunda no momento.")
        else:
            lista_ncs = [f"{nc.id_nc} - {nc.processo_origem}" for nc in ncs_para_causa]
            nc_selecionada = st.selectbox("Selecione a NC para Análise de Causa", lista_ncs)
            
            # CORREÇÃO AQUI TAMBÉM: Garante que busca pelo texto do ID puro
            id_nc_atual = nc_selecionada.split(" - ")[0]
            
            nc_obj = session.query(NaoConformidadeModel).filter_by(id_nc=id_nc_atual).first()
            
            if nc_obj:
                st.info(f"**Desvio:** {nc_obj.descricao_saida}\n\n**Contenção Aplicada:** {nc_obj.detalhes_tratativa}")
                
                st.subheader("🧠 Metodologia dos 5 Porquês")
                p1 = st.text_area("1. Por que o problema aconteceu?", value=nc_obj.porque_1 or "")
                p2 = st.text_area("2. Por que isso ocorreu? (Baseado no Porquê 1)", value=nc_obj.porque_2 or "")
                p3 = st.text_area("3. Por que isso ocorreu? (Baseado no Porquê 2)", value=nc_obj.porque_3 or "")
                p4 = st.text_area("4. Por que isso ocorreu? (Baseado no Porquê 3)", value=nc_obj.porque_4 or "")
                p5 = st.text_area("5. Por que isso ocorreu? (Causa Sistêmica/Raiz)", value=nc_obj.porque_5 or "")
                
                causa_definida = st.text_input("Definição Final da Causa Raiz", value=nc_obj.causa_raiz_definida or "")
                
                st.markdown("---")
                st.subheader("🔒 Autorização de Fechamento")
                doc_retida = st.checkbox("Informação documentada retida na íntegra conforme Cláusula 8.7.2?", value=nc_obj.informacao_documentada_retida)
                
                if st.button("Finalizar e Encerrar Ocorrência"):
                    if causa_definida and p1 and p5:
                        nc_obj.porque_1 = p1
                        nc_obj.porque_2 = p2
                        nc_obj.porque_3 = p3
                        nc_obj.porque_4 = p4
                        nc_obj.porque_5 = p5
                        nc_obj.causa_raiz_definida = causa_definida
                        nc_obj.informacao_documentada_retida = doc_retida
                        nc_obj.status = "Concluído"
                        nc_obj.data_fechamento = datetime.utcnow()
                        nc_obj.autorizado_por = st.session_state["usuario"]
                        
                        id_ap_gerado = verificar_reincidencia_e_gerar_ap(session, nc_obj.processo_origem, causa_definida)
                        
                        session.commit()
                        st.success(f"Ocorrência {id_nc_atual} encerrada com sucesso!")
                        if id_ap_gerado:
                            st.warning(f"🚨 Alerta ISO 9001: Risco recorrente detectado! Plano Preventivo Global **{id_ap_gerado}** foi gerado na fila.")
                        st.rerun()
                    else:
                        st.error("Preencha a análise dos porquês e defina formalmente a causa raiz sistêmica.")
            else:
                st.error("Erro ao carregar os dados desta Não Conformidade.")

    # --- MÓDULO 4: CAUSA RAIZ & FECHAMENTO ---
    elif menu == "Causa Raiz & Fechamento":
        st.title("🔍 Análise de Causa Raiz & Encerramento (Cláusula 10.2)")
        
        ncs_para_causa = session.query(NaoConformidadeModel).filter(NaoConformidadeModel.status == "Em Análise de Causa").all()
        
        if not ncs_para_causa:
            st.info("Nenhuma não conformidade aguardando análise de causa raiz profunda no momento.")
        else:
            lista_ncs = [f"{nc.id_nc} - {nc.processo_origem}" for nc in ncs_para_causa]
            nc_selecionada = st.selectbox("Selecione a NC para Análise de Causa", lista_ncs)
            id_nc_atual = nc_selecionada.split(" - ")[0]
            nc_obj = session.query(NaoConformidadeModel).filter_by(id_nc=id_nc_atual).first()
            
            st.info(f"**Desvio:** {nc_obj.descricao_saida}\n\n**Contenção Aplicada:** {nc_obj.detalhes_tratativa}")
            
            st.subheader("🧠 Metodologia dos 5 Porquês")
            p1 = st.text_area("1. Por que o problema aconteceu?", value=nc_obj.porque_1 or "")
            p2 = st.text_area("2. Por que isso ocorreu? (Baseado no Porquê 1)", value=nc_obj.porque_2 or "")
            p3 = st.text_area("3. Por que isso ocorreu? (Baseado no Porquê 2)", value=nc_obj.porque_3 or "")
            p4 = st.text_area("4. Por que isso ocorreu? (Baseado no Porquê 3)", value=nc_obj.porque_4 or "")
            p5 = st.text_area("5. Por que isso ocorreu? (Causa Sistêmica/Raiz)", value=nc_obj.porque_5 or "")
            
            causa_definida = st.text_input("Definição Final da Causa Raiz", value=nc_obj.causa_raiz_definida or "")
            
            st.markdown("---")
            st.subheader("🔒 Autorização de Fechamento")
            doc_retida = st.checkbox("Informação documentada retida na íntegra conforme Cláusula 8.7.2?", value=nc_obj.informacao_documentada_retida)
            
            if st.button("Finalizar e Encerrar Ocorrência"):
                if causa_definida and p1 and p5:
                    nc_obj.porque_1 = p1
                    nc_obj.porque_2 = p2
                    nc_obj.porque_3 = p3
                    nc_obj.porque_4 = p4
                    nc_obj.porque_5 = p5
                    nc_obj.causa_raiz_definida = causa_definida
                    nc_obj.informacao_documentada_retida = doc_retida
                    nc_obj.status = "Concluído"
                    nc_obj.data_fechamento = datetime.utcnow()
                    nc_obj.autorizado_por = st.session_state["usuario"]
                    
                    # Verificar automaticamente se gerará Plano Preventivo Global (Se houver >= 3 reincidências)
                    id_ap_gerado = verificar_reincidencia_e_gerar_ap(session, nc_obj.processo_origem, causa_definida)
                    
                    session.commit()
                    st.success(f"Ocorrência {id_nc_atual} encerrada com sucesso!")
                    if id_ap_gerado:
                        st.warning(f"🚨 Alerta ISO 9001: Risco recorrente detectado! Plano Preventivo Global **{id_ap_gerado}** foi gerado na fila.")
                    st.rerun()
                else:
                    st.error("Preencha a análise dos porquês e defina formalmente a causa raiz sistêmica.")

    # --- MÓDULO 5: PLANOS PREVENTIVOS ---
    elif menu == "Planos Preventivos":
        st.title("🛡️ Planos de Ação Preventivos / Global (Cláusula 6.1)")
        st.write("Planos preventivos automáticos gerados a partir do histórico de tripla reincidência por setor/causa raiz.")
        
        planos = session.query(AcoesPreventivasModel).all()
        
        if not planos:
            st.info("Nenhum Plano Preventivo Global ativo ou engatilhado por reincidência.")
        else:
            for pl in planos:
                with st.expander(f"📌 {pl.id_ap} - Setor: {pl.processo} ({pl.status})"):
                    st.write(f"**Gatilho de Causa Raiz:** {pl.causa_raiz_gatilho}")
                    st.write(f"**Escopo Regulatório:** {pl.descricao_plano}")
                    st.write(f"**Aberto em:** {pl.data_abertura.strftime('%d/%m/%Y %H:%M')}")
                    
                    if pl.status == "Aberta" and st.session_state["perfil"] == "Gerente":
                        if st.button(f"Iniciar Implantação de Bloqueio - {pl.id_ap}"):
                            pl.status = "Em Execução"
                            session.commit()
                            st.rerun()

    # --- MÓDULO 6: AUDITORIA DE DADOS ---
    elif menu == "Auditoria de Dados":
        st.title("🗂️ Registro Digital Completo para Auditoria Externa")
        st.write("Tabela consolidada e estruturada para rastreabilidade de ponta a ponta.")
        
        ncs_todas = session.query(NaoConformidadeModel).all()
        
        if not ncs_todas:
            st.warning("Não há nenhum registro inserido na base de dados para auditoria.")
        else:
            dados_auditoria = []
            for nc in ncs_todas:
                dados_auditoria.append({
                    "ID NC": nc.id_nc,
                    "Processo": nc.processo_origem,
                    "Identificado Por": nc.responsavel_identificacao,
                    "Impacto": nc.impacto_potencial,
                    "Tratativa Coativa": nc.tratativa_adotada,
                    "Causa Raiz (5º Porquê)": nc.causa_raiz_definida,
                    "Status Atual": nc.status,
                    "Autorizado Por": nc.autorizado_por if nc.autorizado_por else "Aguardando",
                    "Evidência Histórica": "Sim" if nc.informacao_documentada_retida else "Não"
                })
            
            df_auditoria = pd.DataFrame(dados_auditoria)
            st.dataframe(df_auditoria, use_container_width=True)
            
            # Exportador rápido em CSV para conferências fiscais/qualidade
            csv = df_auditoria.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Exportar Relatório de Não Conformidades (RNC)", csv, "rnc_iso9001_auditoria.csv", "text/csv")

