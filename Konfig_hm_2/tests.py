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
import unittest
import os
from visualizer import parse_config, parse_pom, get_all_dependencies, build_graph

class TestDependencyVisualizer(unittest.TestCase):

    def setUp(self):
        # Создаем временные файлы для тестов
        self.test_config = 'test_config.xml'
        with open(self.test_config, 'w') as f:
            f.write('''<?xml version="1.0" encoding="UTF-8"?>
<config>
    <graphviz_path>C:\\usr\\bin\\dot</graphviz_path>
    <package_path>./test_package</package_path>
    <output_image_path>./test_package/output.png</output_image_path>
    <repository_url>https://repo.maven.apache.org/maven2/</repository_url>
</config>''')

        self.test_pom = './test_package/pom.xml'
        os.makedirs('./test_package', exist_ok=True)
        with open(self.test_pom, 'w') as f:
            f.write('''<project xmlns="http://maven.apache.org/POM/4.0.0"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
    https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>test-artifact</artifactId>
    <version>1.0.0</version>
    <dependencies>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.12</version>
        </dependency>
    </dependencies>
</project>''')

    def test_parse_config(self):
        """Тестирует функцию parse_config для корректного парсинга config.xml."""
        graphviz_path, package_path, output_image_path, repository_url = parse_config('./test_config.xml')

        # Нормализуем пути для кросс-платформенной проверки
        expected_graphviz_path = os.path.abspath('C:\\usr\\bin\\dot')
        expected_package_path = os.path.abspath('./test_package')
        expected_output_image_path = os.path.abspath('./test_package/output.png')
        expected_repository_url = 'https://repo.maven.apache.org/maven2/'

        self.assertEqual(graphviz_path, expected_graphviz_path)
        self.assertEqual(package_path, expected_package_path)
        self.assertEqual(output_image_path, expected_output_image_path)
        self.assertEqual(repository_url, expected_repository_url)

    def test_parse_pom(self):
        """Тестирует парсинг POM-файла и извлечение зависимостей."""
        dependencies = parse_pom(self.test_pom)
        self.assertEqual(len(dependencies), 1)
        self.assertEqual(dependencies[0]['group_id'], 'junit')
        self.assertEqual(dependencies[0]['artifact_id'], 'junit')
        self.assertEqual(dependencies[0]['version'], '4.12')

    def test_get_all_dependencies(self):
        """Тестирует извлечение всех зависимостей, включая транзитивные."""
        # Для упрощения теста считаем, что нет транзитивных зависимостей
        dependencies = get_all_dependencies(self.test_pom)
        self.assertEqual(len(dependencies), 1)

    def test_build_graph(self):
        """Тестирует построение графа зависимостей в формате DOT."""
        dependencies = [
            {
                'group_id': 'com.example',
                'artifact_id': 'test-artifact',
                'version': '1.0.0',
                'dependencies': [
                    {
                        'group_id': 'junit',
                        'artifact_id': 'junit',
                        'version': '4.12',
                        'dependencies': []
                    }
                ]
            }
        ]
        graph_lines = build_graph(dependencies)
        expected_lines = [
            'digraph G {',
            'ranksep=2;',
            'nodesep=1.5;',
            '"com.example:test-artifact" -> "junit:junit";'
        ]
        self.assertTrue(all(line in graph_lines for line in expected_lines))

    def tearDown(self):
        # Удаляем временные файлы после тестов
        os.remove(self.test_config)
        os.remove(self.test_pom)
        os.rmdir('./test_package')

if __name__ == '__main__':
    unittest.main()
