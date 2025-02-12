import os
import zipfile
import xmltodict
import pandas as pd
from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.contrib import messages
from .forms import UserRegisterForm
from .models import XMLFile

def home(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()  # Salva o usuário e o perfil
            login(request, user)  # Autentica o usuário após o registro
            return redirect('welcome')  # Redireciona para a página de boas-vindas
    else:
        form = UserRegisterForm()
    return render(request, 'register.html', {'form': form})

def standardize_keys(data, mappings, parent_key=None):
    if isinstance(data, dict):
        standardized = {}
        for k, v in data.items():
            if parent_key == "Servico" and k.lower().startswith("codigo") and "municipio" not in k.lower():
                if k not in mappings:
                    mappings[k] = "CodigoTributacaoMunicipio"
            
            standardized_key = mappings.get(k, k)
            standardized[standardized_key] = standardize_keys(v, mappings, parent_key=k if k == "Servico" else parent_key)
        return standardized
    elif isinstance(data, list):
        return [standardize_keys(item, mappings, parent_key) for item in data]
    else:
        return data

def extract_data_from_xml(file_path, mappings):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            xml_content = file.read()
            print("XML carregado com sucesso!")

            xml_dict = xmltodict.parse(xml_content)
            print("Dicionário convertido do XML:", xml_dict)

            xml_dict = standardize_keys(xml_dict, mappings)

            consultar_nfse_resposta = xml_dict.get('ConsultarNfseResposta')
            if not consultar_nfse_resposta:
                print("Erro: 'ConsultarNfseResposta' não encontrado no XML.")
                return []

            lista_nfse = consultar_nfse_resposta.get('ListaNfse', {}).get('CompNfse', [])
            if not isinstance(lista_nfse, list):
                lista_nfse = [lista_nfse]

            print("Número de notas fiscais encontradas:", len(lista_nfse))

            data_list = []  # Lista para armazenar os dados de todas as notas fiscais
            for comp_nfse in lista_nfse:
                inf_nfse = comp_nfse.get('Nfse', {}).get('InfNfse', {})
                if not inf_nfse:
                    print("Aviso: 'InfNfse' não encontrado em uma nota fiscal.")
                    continue

                prestador = inf_nfse.get('PrestadorServico', {}).get('IdentificacaoPrestador', {})
                cnpj_prestador = prestador.get('Cnpj', '')
                nome_fantasia_prestador = inf_nfse.get('PrestadorServico', {}).get('RazaoSocial', '')
                codigo_tributacao_municipio = inf_nfse.get('Servico', {}).get('CodigoTributacaoMunicipio', '')
                servico = inf_nfse.get('Servico', {})

                valor_servicos = servico.get('Valores', {}).get('ValorServicos', '0')
                valor_servicos = float(valor_servicos) if valor_servicos else 0.0
                iss_retido = servico.get('Valores', {}).get('IssRetido', '2')

                data_atual = datetime.now()
                data_envio = data_atual.strftime('%Y-%m-%d %H:%M:%S')
                data_competencia = '2024-08-01'

                # Adiciona os dados da nota fiscal à lista
                data_list.append({
                    'DataEnvio': data_envio,
                    'CnpjPrestador': cnpj_prestador,
                    'NomeFantasiaPrestador': nome_fantasia_prestador,
                    'DataCompetencia': data_competencia,
                    'CodigoTributacaoMunicipio': codigo_tributacao_municipio,
                    'ValorServicosRetido': valor_servicos if iss_retido == '1' else 0.0,
                    'ValorServicos': valor_servicos if iss_retido != '1' else 0.0,
                })

            print("Dados extraídos do arquivo:", data_list)
            return data_list

    except Exception as e:
        print(f"Erro ao processar o XML: {e}")
        return []
    
@login_required
def welcome(request):
    return render(request, 'welcome.html', {'user': request.user})

def user_logout(request):
    logout(request)
    return redirect('register')

from django.contrib import messages

@login_required
def upload_xml(request):
    if request.method == 'POST':
        all_data = []  # Lista para acumular dados de todos os arquivos
        mappings = {
            "CodigoTributacaoMunicipio": "CodigoTributacaoMunicipio",
            "CodigoCnae": "CodigoTributacaoMunicipio"
        }

        processed_files = []  # Lista de arquivos processados com sucesso
        ignored_files = []    # Lista de arquivos ignorados (inválidos ou sem notas)

        # Verifica se arquivos XML foram enviados
        if 'xml_files' in request.FILES:
            xml_files = request.FILES.getlist('xml_files')  # Recebe múltiplos arquivos
            for xml_file in xml_files:
                print(f"Processando arquivo: {xml_file.name}")

                # Salvar o arquivo XML no banco de dados
                xml_file_instance = XMLFile.objects.create(user=request.user, xml_file=xml_file)
                file_path = os.path.join('media', xml_file_instance.xml_file.name)
                print(f"Arquivo salvo temporariamente em: {file_path}")

                # Processar o XML
                try:
                    data_list = extract_data_from_xml(file_path, mappings)
                    if data_list:
                        all_data.extend(data_list)  # Adiciona os dados à lista geral
                        processed_files.append(xml_file.name)  # Adiciona à lista de processados
                        print(f"Notas válidas encontradas no arquivo {xml_file.name}.")
                    else:
                        ignored_files.append(xml_file.name)  # Adiciona à lista de ignorados
                        print(f"Nenhuma nota válida encontrada no arquivo {xml_file.name}. Ignorando...")
                except Exception as e:
                    ignored_files.append(xml_file.name)  # Adiciona à lista de ignorados
                    print(f"Erro ao processar o arquivo XML {xml_file.name}: {e}. Ignorando...")

        # Verifica se um arquivo ZIP foi enviado
        elif 'zip_file' in request.FILES:
            zip_file = request.FILES['zip_file']
            print(f"Processando arquivo ZIP: {zip_file.name}")

            # Salvar o arquivo ZIP temporariamente
            zip_path = os.path.join('media', zip_file.name)
            with open(zip_path, 'wb+') as destination:
                for chunk in zip_file.chunks():
                    destination.write(chunk)

            # Extrair o ZIP e processar os arquivos XML
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall('media/extracted')
                print(f"Arquivos extraídos para: media/extracted")

                for extracted_file in zip_ref.namelist():
                    if extracted_file.endswith('.xml'):
                        file_path = os.path.join('media/extracted', extracted_file)
                        print(f"Processando arquivo extraído: {extracted_file}")

                        try:
                            data_list = extract_data_from_xml(file_path, mappings)
                            if data_list:
                                all_data.extend(data_list)  # Adiciona os dados à lista geral
                                processed_files.append(extracted_file)  # Adiciona à lista de processados
                                print(f"Notas válidas encontradas no arquivo {extracted_file}.")
                            else:
                                ignored_files.append(extracted_file)  # Adiciona à lista de ignorados
                                print(f"Nenhuma nota válida encontrada no arquivo {extracted_file}. Ignorando...")
                        except Exception as e:
                            ignored_files.append(extracted_file)  # Adiciona à lista de ignorados
                            print(f"Erro ao processar o arquivo XML {extracted_file}: {e}. Ignorando...")

        else:
            messages.error(request, "Nenhum arquivo enviado.")
            return redirect('welcome')

        # Verifica se pelo menos uma nota válida foi encontrada
        if not all_data:
            messages.error(request, "Nenhuma nota fiscal válida encontrada.")
            return redirect('welcome')

        # Gerar o DataFrame com todos os dados acumulados
        df = pd.DataFrame(all_data)
        print("DataFrame criado com sucesso!")

        # Gerar arquivo Excel
        output_file = os.path.join('media', 'notas_fiscais_nfse.xlsx')
        df.to_excel(output_file, index=False)
        print(f"Arquivo Excel gerado: {output_file}")

        # Feedback ao usuário
        if processed_files:
            messages.success(request, f"Arquivos processados com sucesso: {', '.join(processed_files)}")
        if ignored_files:
            messages.warning(request, f"Arquivos ignorados: {', '.join(ignored_files)}")

        # Enviar o arquivo Excel gerado
        with open(output_file, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="notas_fiscais_nfse.xlsx"'
            return response

    return redirect('welcome')