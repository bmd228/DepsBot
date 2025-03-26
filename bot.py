import os
import shutil
import subprocess
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InputFile,FSInputFile
from aiohttp import web
from pathlib import Path
from io import BytesIO
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "your_token_here")
EXTERNAL_ADDR = os.getenv("IP_ADDRES", "localhost")
bot = Bot(token=TOKEN,timeout=1800)
dp = Dispatcher()

BASE_DIR = "/app/packages"
os.makedirs(BASE_DIR, exist_ok=True)

SUPPORTED_UBUNTU_VERSIONS = {
    "25.04": "plucky",
    "24.10": "oracular",
    "24.04": "noble",
    "22.04": "jammy",
    "20.04": "focal",
    "18.04": "bionic"
}

SUPPORTED_DEBIAN_VERSIONS = {
    "10": "buster",
    "11": "bullseye",
    "12": "bookworm",
    "13": "trixie",
    "14": "forky"
}

# Функция для создания chroot-окружения внутри контейнера
def setup_chroot_ubuntu(ubuntu_codename):
    chroot_path = f"/srv/chroot/{ubuntu_codename}"
    
    if not os.path.exists(chroot_path):
        subprocess.run(
            ["debootstrap", "--arch=amd64", ubuntu_codename, chroot_path, "http://archive.ubuntu.com/ubuntu/"],
            check=True
        )
# Функция для создания chroot-окружения внутри контейнера
def setup_chroot_debian(debian_codename):
    chroot_path = f"/srv/chroot/{debian_codename}"
    
    if not os.path.exists(chroot_path):
        subprocess.run(
            ["debootstrap", "--arch=amd64", debian_codename, chroot_path, "http://deb.debian.org/debian/"],
            check=True
        )
# Функция для добавления кастомного репозитория в sources.list
def add_custom_repo(codename, str_repo):
    sources_list_path = f"/srv/chroot/{codename}/etc/apt/sources.list"
    
    # # Проверяем, существует ли уже такой репозиторий
    # with open(sources_list_path, "r") as f:
    #     sources = f.readlines()
    #     if f"{type} [trusted=yes] {repo_url} {ubuntu_codename} main" in sources:
    #         return f"Репозиторий {repo_url} уже добавлен."
    
    # Добавляем репозиторий в sources.list
    with open(sources_list_path, "a") as f:
        f.write(f"{str_repo}\n")
    #chroot_cmd = f"chroot /srv/chroot/{codename} apt update --allow-unauthenticated"
    chroot_cmd = f"chroot /srv/chroot/{codename} /bin/bash -c 'apt update --allow-unauthenticated'"
    
    result = subprocess.run(chroot_cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        return f"Ошибка обновления репозитория: {result.stderr}"

    return f"Репозиторий {str_repo} добавлен в sources.list."
# Функция для удаления кастомного репозитория из sources.list
def remove_custom_repo(codename, num_str:int):
    sources_list_path = f"/srv/chroot/{codename}/etc/apt/sources.list"
    if not os.path.exists(sources_list_path):
        return f"Файл {sources_list_path} не найден."

    with open(sources_list_path, "r") as f:
        sources = f.readlines()

    if  num_str > len(sources):
        return f"Ошибка: номер строки {num_str} выходит за пределы [1, {len(sources)}]."

    del sources[num_str - 1]  # Удаляем строку (нумерация в списке с 0)

    with open(sources_list_path, "w") as f:
        f.writelines(sources)
   
    #chroot_cmd = f"chroot /srv/chroot/{codename} apt update --allow-unauthenticated"
    
    chroot_cmd = f"chroot /srv/chroot/{codename} /bin/bash -c 'apt update --allow-unauthenticated'"
    
    result = subprocess.run(chroot_cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        return f"Ошибка обновления репозитория: {result.stderr}"
    
    return f"Репозиторий {sources[num_str - 1]} удален."

# Функция для вывода всех кастомных репозиториев
def list_custom_repos(сodename):
    sources_list_path = f"/srv/chroot/{сodename}/etc/apt/sources.list"
    
    with open(sources_list_path, "r") as f:
        sources = f.readlines()
    
    repos = [line for line in sources if line.startswith("deb")]
    
    if not repos:
        return "Нет добавленных кастомных репозиториев."
    
    return "\n".join(repos)
@dp.message(Command("addrepo"))
async def add_repo(message: types.Message):
    try:
        # Получаем список пакетов и версию Ubuntu из сообщения
        _, os,version, *str_repo = message.text.split()
        chat_id = message.chat.id  # Получаем ID чата для отправки обновлений
        
        if not str_repo:
            await message.reply("Пожалуйста, укажите строку, например: deb [trusted=yes] http://archive.ubuntu.com/ubuntu jammy main.")
            return
        if os =="ubuntu":
            if version not in SUPPORTED_UBUNTU_VERSIONS:
                await message.reply(f"Версия Ubuntu {version} не поддерживается.")
                return
        elif os=="debian":
            if version not in SUPPORTED_DEBIAN_VERSIONS:
                await message.reply(f"Версия Debian {version} не поддерживается.")
                return
        else:
            await message.reply(f"Операционна сиситема не поддерживается.")
            return
        codename=str()
        if os =="ubuntu":
            codename = SUPPORTED_UBUNTU_VERSIONS[version]
        elif os=="debian":
            codename = SUPPORTED_DEBIAN_VERSIONS[version]
        result = add_custom_repo(codename, " ".join(str_repo))
        
        await message.reply(result)
    
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")

@dp.message(Command("delrepo"))
async def del_repo(message: types.Message):
    try:
        # Получаем список пакетов и версию Ubuntu из сообщения
        _, os,version, num_str = message.text.split()
        chat_id = message.chat.id  # Получаем ID чата для отправки обновлений
        
        if not num_str:
            await message.reply("Пожалуйста, укажите номер строки, которую необходимо удалить.")
            return
        if os =="ubuntu":
            if version not in SUPPORTED_UBUNTU_VERSIONS:
                await message.reply(f"Версия Ubuntu {version} не поддерживается.")
                return
        elif os=="debian":
            if version not in SUPPORTED_DEBIAN_VERSIONS:
                await message.reply(f"Версия Debian {version} не поддерживается.")
                return
        else:
            await message.reply(f"Операционна сиситема не поддерживается.")
            return
        codename=str()
        if os =="ubuntu":
            codename = SUPPORTED_UBUNTU_VERSIONS[version]
        elif os=="debian":
            codename = SUPPORTED_DEBIAN_VERSIONS[version]
        result = remove_custom_repo(codename, int(num_str))
        
        await message.reply(result)
    
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")

@dp.message(Command("listrepos"))
async def list_repos(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.reply("Использование: /listrepos [операционная_система] [версия]")
            return
        
        _,os, version = parts
        codename=str()
        if os =="ubuntu":
            if version not in SUPPORTED_UBUNTU_VERSIONS:
                await message.reply(f"Версия Ubuntu {version} не поддерживается.")
                return
        elif os=="debian":
            if version not in SUPPORTED_DEBIAN_VERSIONS:
                await message.reply(f"Версия Debian {version} не поддерживается.")
                return
        else:
            await message.reply(f"Операционна сиситема не поддерживается.")
            return
        if os =="ubuntu":
            codename = SUPPORTED_UBUNTU_VERSIONS[version]
        elif os=="debian":
            codename = SUPPORTED_DEBIAN_VERSIONS[version]
        repos = list_custom_repos(codename)
        await message.reply(repos)
    
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")
@dp.message(Command("clear"))
async def clear(message: types.Message):
    try:
        shutil.rmtree(BASE_DIR)
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")    
# Функция для обновления прогресса
async def update_progress(chat_id, message):
    await bot.send_message(chat_id, message)
@dp.message(Command("help"))
async def help_command(message: types.Message):
    help_text = (
        "Привет! Вот список доступных команд:\n\n"
        "/getpkg [операционная_система] [версия] [пакеты]...  - скачивание пакета для указанной версии.\n"
        "/getdocker [докер образ]  - докер образа.\n"
        "/getpy [операционная_система] [версия python] [пакеты]...  - скачивание пакетов для python.\n"
        "/searchpkg [операционная_система] [версия] [пакет] - поиск пакетов в репозитории\n"
        "/addrepo [операционная_система] [версия] [строка source_list] - добавление кастомного репозитория в sources.list.\n"
        "/delrepo [операционная_система] [версия] [номер_строки] - удаление кастомного репозитория из sources.list.\n"
        "/listrepos [операционная_система] [версия] - просмотр всех добавленных кастомных репозиториев для указанной версии.\n"
        "/clearall - отчистить все \n"
        "/clear - отчистить базовую директорию \n\n"
        "Пример использования:\n"
        "/addrepo ubuntu 22.04 deb [trusted=yes] http://archive.ubuntu.com/ubuntu jammy main) - добавление кастомного репозитория.\n"
        "/delrepo ubuntu 22.04 2 - удаление кастомного репозитория.\n"
        "/listrepos ubuntu 22.04 - просмотр репозиториев.\n\n"
        "Операционные системы: debian или ubuntu."
    )
    await message.reply(help_text)

# Функция для скачивания пакетов внутри chroot
async def download_packages_ubuntu(pkg_names, ubuntu_version, chat_id):
    if ubuntu_version not in SUPPORTED_UBUNTU_VERSIONS:
        return None, f"Версия Ubuntu {ubuntu_version} не поддерживается."

    ubuntu_codename = SUPPORTED_UBUNTU_VERSIONS[ubuntu_version]
    setup_chroot_ubuntu(ubuntu_codename)

    work_dir = os.path.join(BASE_DIR, f"{'_'.join(pkg_names)}_{ubuntu_codename}")
    os.makedirs(work_dir, exist_ok=True)

    archive_path = f"{work_dir}.tar.gz"
    
    if os.path.exists(archive_path):
        return archive_path, None

    # Обновляем сообщение о процессе
    await update_progress(chat_id, "Создание chroot-окружения...")

    # Собираем команду для скачивания нескольких пакетов
    pkg_list = " ".join(pkg_names)
    #chroot_cmd = f"chroot /srv/chroot/{ubuntu_codename} apt-get -y install --allow-unauthenticated --download-only {pkg_list}"
    chroot_cmd = f"chroot /srv/chroot/{ubuntu_codename} /bin/bash -c 'apt-get -y install --allow-unauthenticated --download-only {pkg_list}'"
    
    result = subprocess.run(chroot_cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        return None, f"Ошибка при скачивании пакетов: {result.stderr}"

    # Обновляем сообщение о скачивании пакетов
    await update_progress(chat_id, "Скачивание пакетов...")

    # Переносим скачанные пакеты
    cache_dir = f"/srv/chroot/{ubuntu_codename}/var/cache/apt/archives/"
    for file in os.listdir(cache_dir):
        if file.endswith(".deb"):
            shutil.move(os.path.join(cache_dir, file), work_dir)

    # Обновляем сообщение о завершении процесса
    await update_progress(chat_id, "Создание архива...")

    # Упаковываем в архив
    shutil.make_archive(work_dir, "gztar", work_dir)
    shutil.rmtree(work_dir)
    return archive_path, None
# Функция для скачивания пакетов внутри chroot
async def download_packages_debian(pkg_names, debian_version, chat_id):
    if debian_version not in SUPPORTED_DEBIAN_VERSIONS:
        return None, f"Версия Debian {debian_version} не поддерживается."

    debian_codename = SUPPORTED_DEBIAN_VERSIONS[debian_version]
    setup_chroot_debian(debian_codename)

    work_dir = os.path.join(BASE_DIR, f"{'_'.join(pkg_names)}_{debian_codename}")
    os.makedirs(work_dir, exist_ok=True)

    archive_path = f"{work_dir}.tar.gz"
    
    if os.path.exists(archive_path):
        return archive_path, None

    # Обновляем сообщение о процессе
    await update_progress(chat_id, "Создание chroot-окружения...")

    # Собираем команду для скачивания нескольких пакетов
    pkg_list = " ".join(pkg_names)
    #chroot_cmd = f"chroot /srv/chroot/{debian_codename} apt-get -y install --allow-unauthenticated --download-only {pkg_list}"
    chroot_cmd = f"chroot /srv/chroot/{debian_codename} /bin/bash -c 'apt-get -y install --allow-unauthenticated --download-only {pkg_list}'"
    
    result = subprocess.run(chroot_cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        return None, f"Ошибка при скачивании пакетов: {result.stderr}"

    # Обновляем сообщение о скачивании пакетов
    await update_progress(chat_id, "Скачивание пакетов...")

    # Переносим скачанные пакеты
    cache_dir = f"/srv/chroot/{debian_codename}/var/cache/apt/archives/"
    for file in os.listdir(cache_dir):
        if file.endswith(".deb"):
            shutil.move(os.path.join(cache_dir, file), work_dir)

    # Обновляем сообщение о завершении процесса
    await update_progress(chat_id, "Создание архива...")

    # Упаковываем в архив
    shutil.make_archive(work_dir, "gztar", work_dir)
    shutil.rmtree(work_dir)
    return archive_path, None
@dp.message(Command("clearall"))
async def clear_all(message: types.Message):
    try:
        shutil.rmtree("/srv/chroot/")
        shutil.rmtree(BASE_DIR)
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")    
# Функция для обновления прогресса
async def update_progress(chat_id, message):
    await bot.send_message(chat_id, message)
    
@dp.message(Command("searchpkg"))
async def search_package(message: types.Message):
    try:
        # Получаем аргументы команды
        args = message.text.split(maxsplit=3)
        
        if len(args) < 4:
            await message.reply("Пожалуйста, укажите ключевое слово для поиска, операционную систему и версию.")
            return
        
        search_term = args[3]
        version = args[2]
        os = args[1]
        chat_id = message.chat.id  # Получаем ID чата для отправки обновлений

        if os =="ubuntu":
            if version not in SUPPORTED_UBUNTU_VERSIONS:
                await message.reply(f"Версия Ubuntu {version} не поддерживается.")
                return
        elif os=="debian":
            if version not in SUPPORTED_DEBIAN_VERSIONS:
                await message.reply(f"Версия Debian {version} не поддерживается.")
                return
        else:
            await message.reply(f"Операционна сиситема не поддерживается.")
            return
        
        codename=str()
        if os=="ubuntu":
            codename = SUPPORTED_UBUNTU_VERSIONS[version]
            # Убедимся, что chroot окружение настроено
            setup_chroot_ubuntu(codename)
        elif os=="debian":
            codename = SUPPORTED_DEBIAN_VERSIONS[version]
            # Убедимся, что chroot окружение настроено
            setup_chroot_debian(codename)
        
        # Выполнение команды поиска пакета через apt-cache внутри chroot
        chroot_cmd = f"chroot /srv/chroot/{codename} /bin/bash -c 'apt update && apt search {search_term}'"
        
        result = subprocess.run(chroot_cmd, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            await message.reply(f"Ошибка при поиске пакета: {result.stderr}")
        else:
            # Выводим результаты поиска
            search_results = result.stdout.strip()
            if search_results:
                max_length = 4096
                if len(search_results)>max_length:
                    bio = BytesIO(search_results.encode("utf-8"))
                    bio.name = "output.txt"
                    await message.reply_document(types.BufferedInputFile(bio.getvalue(), filename="output.txt"))
                else:
                    await message.reply(search_results)
                #await message.reply(f"Результаты поиска для '{search_term}' в Ubuntu {ubuntu_version}:\n\n{search_results}")
            else:
                await message.reply(f"Не найдено пакетов, соответствующих '{search_term}' в {os} {version}.")
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")

@dp.message(Command("getpy"))
async def get_python_package(message: types.Message):
    try:
        _, os,version, *pkg_names = message.text.split()
        chat_id=message.chat.id
        if not pkg_names:
            await message.reply("Пожалуйста, укажите хотя бы один пакет для скачивания.")
            return
        platform=str()
        if os=="win":
            platform='win_amd64'
        elif os=="linux":
            platform='manylinux2014_x86_64'
        else:
            await message.reply(f"Операционна сиситема не поддерживается.")
            return
        if not version.isdigit():
            await message.reply("Укажите версию Python (например, 38, 310, 312) БЕЗ ТОЧЕК!!!.")
            return
        
        download_dir = f"{BASE_DIR}/{'_'.join(pkg_names)}_{os}_{version}"
        download_path = Path(download_dir)
        if not download_path.exists():
            download_path.mkdir(parents=True, exist_ok=True)
        pip_cmd = f"pip download --prefer-binary --only-binary=:all: --python-version {version} --platform {platform} -d {download_dir} {' '.join(pkg_names)}"
        
        result = subprocess.run(pip_cmd, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            await message.reply(f"Ошибка при скачивании python пакетов: {result.stderr}")
            return
        
         # Создание архива
        archive_name = f"{'_'.join(pkg_names)}_{os}_{version}.tar.gz"
        archive_path = f"{BASE_DIR}/{archive_name}"

        # Упаковка скачанных пакетов в архив
        shutil.make_archive(archive_path.replace('.tar.gz', ''), 'gztar', download_dir)
        shutil.rmtree(download_dir)
        await message.reply(f"Пакеты '{' '.join(pkg_names)}' был успешно скачаны и упакованы в архив '{archive_name}'.")
        download_url = f"http://{EXTERNAL_ADDR}:8080/download?file_path={archive_path}"
        await message.reply(f"[Ваши пакеты доступены для скачивания]({download_url})")
        #chat_id = message.chat.id  # Получаем ID чата для отправки обновлений
        
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")
        
@dp.message(Command("getdocker"))
async def get_docker_image(message: types.Message):
    try:
        # Получаем имя Docker образа из команды
        args = message.text.split(maxsplit=2)
        
        if len(args) < 2:
            await message.reply("Пожалуйста, укажите имя Docker образа для скачивания.")
            return
        
        docker_image = args[1]
        chat_id = message.chat.id  # Получаем ID чата для отправки обновлений

        # Скачиваем образ с помощью skopeo
        #skopeo_cmd = f"skopeo copy docker://docker.io/library/{docker_image} dir:{download_dir}"
        filename=str(docker_image)
        filename=filename.replace("/", "_").replace(":", "_")+ ".tar"
        skopeo_cmd = f"skopeo copy docker://{docker_image} docker-archive:{BASE_DIR}/{filename}"
        result = subprocess.run(skopeo_cmd, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            await message.reply(f"Ошибка при скачивании Docker образа: {result.stderr}")
            return

        await message.reply(f"Образ Docker '{docker_image}' был успешно скачан и упакован в архив '{filename}'.")

        # Перемещаем архив в нужную директорию
        archive_path = f"{BASE_DIR}/{filename}"
        download_url = f"http://{EXTERNAL_ADDR}:8080/download?file_path={archive_path}"

        await message.reply(f"[Ваш Docker образ доступен для скачивания]({download_url})")#, parse_mode="Markdown")
    
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")

# Обработчик команды
@dp.message(Command("getpkg"))
async def get_package(message: types.Message):
    try:
        # Получаем список пакетов и версию Ubuntu из сообщения
        _, os,version, *pkg_names = message.text.split()
        chat_id = message.chat.id  # Получаем ID чата для отправки обновлений
        
        if not pkg_names:
            await message.reply("Пожалуйста, укажите хотя бы один пакет для скачивания.")
            return
        if os =="ubuntu":
            if version not in SUPPORTED_UBUNTU_VERSIONS:
                await message.reply(f"Версия Ubuntu {version} не поддерживается.")
                return
        elif os=="debian":
            if version not in SUPPORTED_DEBIAN_VERSIONS:
                await message.reply(f"Версия Debian {version} не поддерживается.")
                return
        else:
            await message.reply(f"Операционна сиситема не поддерживается.")
            return
       
        # Скачиваем несколько пакетов и создаем архив
        if os =="ubuntu":
            archive_path, error = await download_packages_ubuntu(pkg_names, version, chat_id)
        elif os=="debian":
            archive_path, error = await download_packages_debian(pkg_names, version, chat_id)
        
        if error:
            await message.reply(error)
        else:
            # Отправляем ссылку на скачивание
            download_url = f"http://{EXTERNAL_ADDR}:8080/download?file_path={archive_path}"
            await message.reply(f"[Ваш файл доступен для скачивания]({download_url})")

    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")


# Функция для обработки HTTP-запросов (отправка файла по HTTP)
async def handle(request):
    file_path = Path(BASE_DIR) / request.query.get("file_path", "")
    file_name=Path(file_path).name
    if file_path.exists():
        return web.FileResponse(
            file_path, 
            headers={"Content-Disposition": f'attachment; filename="{file_name}"'}
        )
    else:
        return web.Response(text="Файл не найден", status=404)
        
# Запуск HTTP-сервера
async def start_http_server():
    app = web.Application()
    app.router.add_get("/download", handle)  # Пример URL для скачивания файла
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)  # Слушаем порт 8080
    await site.start()
    
# Запуск бота
async def main():
    print("Бот и HTTP сервер запущены...")
    # Запуск HTTP-сервера в фоновом режиме
    asyncio.create_task(start_http_server())
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
