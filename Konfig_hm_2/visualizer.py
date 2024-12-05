import os
import xml.etree.ElementTree as ET
import subprocess
import tempfile
from collections import defaultdict

# Настройка путей и логирование
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_config(config_path: str):
    """Парсит конфигурационный файл и возвращает необходимые параметры."""
    try:
        tree = ET.parse(config_path)
        root = tree.getroot()
        graphviz_path = root.find('graphviz_path').text
        package_path = root.find('package_path').text
        output_image_path = root.find('output_image_path').text
        repository_url = root.find('repository_url').text

        # Преобразуем пути в абсолютные
        graphviz_path = os.path.abspath(graphviz_path)
        package_path = os.path.abspath(package_path)
        output_image_path = os.path.abspath(output_image_path)

        logger.info(f"Путь к Graphviz: {graphviz_path}")
        logger.info(f"Путь к пакету: {package_path}")
        logger.info(f"Путь к изображению: {output_image_path}")
        logger.info(f"URL репозитория: {repository_url}")

        return graphviz_path, package_path, output_image_path, repository_url
    except Exception as e:
        logger.error(f"Ошибка при парсинге конфигурационного файла: {e}")
        raise


def parse_pom(pom_path: str):
    """Парсит pom.xml и возвращает список зависимостей."""
    try:
        tree = ET.parse(pom_path)
        root = tree.getroot()
        # Пространство имен Maven
        namespace = {'ns': 'http://maven.apache.org/POM/4.0.0'}
        dependencies = []

        # Извлекаем версии из parent, если они указаны
        parent_version = root.find('.//ns:parent/ns:version', namespace)
        parent_version = parent_version.text if parent_version is not None else None

        for dependency in root.findall('.//ns:dependency', namespace):
            group_id = dependency.find('ns:groupId', namespace)
            artifact_id = dependency.find('ns:artifactId', namespace)
            version = dependency.find('ns:version', namespace)

            # Если версия отсутствует, наследуем её из parent
            if version is None or version.text is None:
                version = parent_version

            dependencies.append({
                'group_id': group_id.text if group_id is not None else 'N/A',
                'artifact_id': artifact_id.text if artifact_id is not None else 'N/A',
                'version': version if isinstance(version, str) else version.text if version is not None else 'N/A'
            })
        return dependencies
    except Exception as e:
        logger.error(f"Ошибка при парсинге {pom_path}: {e}")
        return []


def find_pom_file(dependency):
    """Ищет pom-файл зависимости в локальном репозитории Maven."""
    m2_repo = os.path.expanduser('~/.m2/repository')
    group_path = dependency['group_id'].replace('.', '/')
    artifact = dependency['artifact_id']
    version = dependency['version']
    pom_path = os.path.join(m2_repo, group_path, artifact, version, f'{artifact}-{version}.pom')
    if os.path.exists(pom_path):
        return pom_path
    else:
        logger.warning(f"Файл pom.xml для зависимости {dependency['group_id']}:{dependency['artifact_id']}:{dependency['version']} не найден.")
        return None


def get_all_dependencies(pom_path, visited=None):
    """Рекурсивно получает все зависимости, включая транзитивные."""
    if visited is None:
        visited = set()
    logger.info(f"Обработка POM: {pom_path}")
    current_dependencies = parse_pom(pom_path)
    all_dependencies = []
    for dep in current_dependencies:
        dep_id = (dep['group_id'], dep['artifact_id'], dep['version'])
        if dep_id not in visited:
            visited.add(dep_id)
            logger.info(f"Найдена зависимость: {dep}")
            dep_pom_path = find_pom_file(dep)
            if dep_pom_path:
                dep['dependencies'] = get_all_dependencies(dep_pom_path, visited)
            else:
                dep['dependencies'] = []
            all_dependencies.append(dep)
    return all_dependencies


def build_graph(dependencies, graph_lines=None, parent_node=None):
    """Строит граф зависимостей в формате DOT."""
    if graph_lines is None:
        graph_lines = [
            'digraph G {',
            'ranksep=2;',  # Увеличиваем вертикальные расстояния
            'nodesep=1.5;',  # Увеличиваем расстояния между узлами
        ]
    for dep in dependencies:
        current_node = f"{dep['group_id']}:{dep['artifact_id']}"
        if parent_node:
            graph_lines.append(f'"{parent_node}" -> "{current_node}";')
        if dep.get('dependencies'):
            build_graph(dep['dependencies'], graph_lines, current_node)
    return graph_lines


def visualize_graph(graphviz_path: str, graph_data: str, output_image_path: str):
    """Визуализирует граф с помощью Graphviz и сохраняет изображение в указанный путь."""
    try:
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.dot', delete=False) as dot_file:
            dot_file.write(graph_data)
            dot_file_path = dot_file.name

        subprocess.run([graphviz_path, '-Tpng', dot_file_path, '-o', output_image_path], check=True)
        logger.info(f"Графическое изображение создано: {output_image_path}")
    except Exception as e:
        logger.error(f"Ошибка при визуализации графа: {e}")
        raise


def main():
    try:
        config_path = 'config.xml'
        graphviz_path, package_path, output_image_path, repository_url = parse_config(config_path)
        pom_path = os.path.join(package_path, 'pom.xml')
        if not os.path.exists(pom_path):
            logger.error(f"Файл pom.xml не найден в {package_path}")
            return
        root_dependencies = get_all_dependencies(pom_path)
        graph_lines = build_graph(root_dependencies)
        graph_lines.append('}')
        graph_data = '\n'.join(graph_lines)
        visualize_graph(graphviz_path, graph_data, output_image_path)
    except Exception as e:
        logger.error(f"Ошибка в выполнении программы: {e}")


if __name__ == '__main__':
    main()
