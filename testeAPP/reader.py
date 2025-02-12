import os
import xmltodict
import pandas as pd
from datetime import datetime

def list_xml_files(directory):
    files = os.listdir(directory)
    xml_files = [f for f in files if f.endswith('.xml')]
    return xml_files

def standardize_keys(data, mappings, parent_key=None):
    """
    Padroniza as chaves do dicionário de acordo com os mapeamentos fornecidos.
    Apenas adiciona ao mapeamento chaves relacionadas ao CNAE (ex.: CodigoTributacaoMuni).

    :data: Dicionário representando o XML.
    :mappings: Dicionário de mapeamento de chaves.
    :parent_key: Nome da chave pai (para verificar se está dentro de "Servico").
    :return: Dicionário com chaves padronizadas.
    """
    if isinstance(data, dict):
        standardized = {}
        for k, v in data.items():
            # Verifica se estamos no contexto de "Servico" e se a chave é relevante ao CNAE
            if parent_key == "Servico" and k.lower().startswith("codigo") and "municipio" not in k.lower():
                if k not in mappings:
                    mappings[k] = "CodigoTributacaoMunicipio"  # Padronizar para "CodigoTributacaoMunicipio"
                    print(f"Novo mapping adicionado: {k} -> CodigoTributacaoMunicipio")
            
            # Substituir chave pelo mapeamento, ou manter a chave original
            standardized_key = mappings.get(k, k)
            
            # Processar valores recursivamente, passando o contexto
            standardized[standardized_key] = standardize_keys(v, mappings, parent_key=k if k == "Servico" else parent_key)
        return standardized
    elif isinstance(data, list):
        return [standardize_keys(item, mappings, parent_key) for item in data]
    else:
        return data

def extract_data_from_xml(file_path, mappings):
    with open(file_path, 'r', encoding='utf-8') as file:
        xml_content = file.read()
        xml_dict = xmltodict.parse(xml_content)
        
        # Padronizar as chaves do XML
        xml_dict = standardize_keys(xml_dict, mappings)
        
        consultar_nfse_resposta = xml_dict.get('ConsultarNfseResposta')
        if not consultar_nfse_resposta:
            return []
        
        lista_nfse = consultar_nfse_resposta.get('ListaNfse', {}).get('CompNfse', [])
        
        if not isinstance(lista_nfse, list):
            lista_nfse = [lista_nfse]
        
        data_dict = {}
        
        for comp_nfse in lista_nfse:
            inf_nfse = comp_nfse.get('Nfse', {}).get('InfNfse', {})
            prestador = inf_nfse.get('PrestadorServico', {}).get('IdentificacaoPrestador', {})
            cnpj_prestador = prestador.get('Cnpj', '')
            nome_fantasia_prestador = inf_nfse.get('PrestadorServico', {}).get('RazaoSocial', '')

            codigo_tributacao_municipio = inf_nfse.get('Servico', {}).get('CodigoTributacaoMunicipio', '')

            servico = inf_nfse.get('Servico', {})
            valor_servicos = servico.get('Valores', {}).get('ValorServicos', '0')
            valor_servicos = float(valor_servicos) if valor_servicos else 0.0
            
            iss_retido = servico.get('Valores', {}).get('IssRetido')
            iss_retido = iss_retido if iss_retido is not None else '2'

            data_atual = datetime.now()
            data_envio = data_atual.strftime('%Y-%m-%d %H:%M:%S')

            data_competencia = '2024-08-01'

            if codigo_tributacao_municipio not in data_dict:
                data_dict[codigo_tributacao_municipio] = {
                    'DataEnvio': data_envio,
                    'CnpjPrestador': cnpj_prestador,
                    'NomeFantasiaPrestador': nome_fantasia_prestador,
                    'DataCompetencia': data_competencia,
                    'CodigoTributacaoMunicipio': codigo_tributacao_municipio,
                    'ValorServicosRetido': 0.0,
                    'ValorServicos': 0.0,
                }

            if iss_retido == '1':
                data_dict[codigo_tributacao_municipio]['ValorServicosRetido'] += valor_servicos
            else:
                data_dict[codigo_tributacao_municipio]['ValorServicos'] += valor_servicos
                    
        data_list = list(data_dict.values())
        return data_list

def main():
    directory = input("Digite o caminho do diretório onde os arquivos XML estão localizados: ")
    directory_rel = "./relatorios"
    xml_files = list_xml_files(directory)
    
    mappings = {
        "CodigoTributacaoMunicipio": "CodigoTributacaoMunicipio",
        "CodigoCnae":"CodigoTributacaoMunicipio"
    }

    if not xml_files:
        print("Nenhum arquivo XML encontrado no diretório especificado.")
        return
    
    all_data = []
    for xml_file in xml_files:
        file_path = os.path.join(directory, xml_file)
        try:
            data = extract_data_from_xml(file_path, mappings)
            all_data.extend(data)
        except Exception as e:
            print(f"Erro ao processar o arquivo {xml_file}: {e}")
    
    if not all_data:
        print("Nenhuma nota fiscal válida encontrada.")
        return
    
    print(all_data)
    print(mappings)
    #df = pd.DataFrame(all_data)
    
    # Adicionar coluna com a proporção de valores retidos
    #df['ProporcaoRetido'] = df.apply(lambda row: row['ValorServicosRetido'] / (row['ValorServicos'] + row['ValorServicosRetido']) if (row['ValorServicos'] + row['ValorServicosRetido']) != 0 else 0, axis=1)
    
    #output_file = os.path.join(directory_rel, 'notas_fiscais_nfse.xlsx')
    #df.to_excel(output_file, index=False)
    #print(f"Planilha gerada com sucesso: {output_file}")
