import os
import shutil
import subprocess
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InputFile,FSInputFile
from aiohttp import web
from pathlib import Path

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

# Функция для создания chroot-окружения внутри контейнера
def setup_chroot(ubuntu_codename):
    chroot_path = f"/srv/chroot/{ubuntu_codename}"
    
    if not os.path.exists(chroot_path):
        subprocess.run(
            ["debootstrap", "--arch=amd64", ubuntu_codename, chroot_path, "http://archive.ubuntu.com/ubuntu/"],
            check=True
        )
# Функция для добавления кастомного репозитория в sources.list
def add_custom_repo(ubuntu_codename, repo_url):
    sources_list_path = f"/srv/chroot/{ubuntu_codename}/etc/apt/sources.list"
    
    # Проверяем, существует ли уже такой репозиторий
    with open(sources_list_path, "r") as f:
        sources = f.readlines()
        if f"deb [trusted=yes] {repo_url} {ubuntu_codename} main" in sources:
            return f"Репозиторий {repo_url} уже добавлен."
    
    # Добавляем репозиторий в sources.list
    with open(sources_list_path, "a") as f:
        f.write(f"deb [trusted=yes] {repo_url} {ubuntu_codename} main\n")
    chroot_cmd = f"chroot /srv/chroot/{ubuntu_codename} apt update --allow-unauthenticated"
    
    result = subprocess.run(chroot_cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        return f"Ошибка обновления репозитория: {result.stderr}"

    return f"Репозиторий {repo_url} добавлен в sources.list."
# Функция для удаления кастомного репозитория из sources.list
def remove_custom_repo(ubuntu_codename, repo_url):
    sources_list_path = f"/srv/chroot/{ubuntu_codename}/etc/apt/sources.list"
    
    with open(sources_list_path, "r") as f:
        sources = f.readlines()
    
    # Ищем строку с репозиторием и удаляем её
    repo_line = f"deb [trusted=yes] {repo_url} {ubuntu_codename} main\n"
    if repo_line in sources:
        sources.remove(repo_line)
        
        with open(sources_list_path, "w") as f:
            f.writelines(sources)
        chroot_cmd = f"chroot /srv/chroot/{ubuntu_codename} apt update --allow-unauthenticated"
    
        result = subprocess.run(chroot_cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            return f"Ошибка обновления репозитория: {result.stderr}"
        return f"Репозиторий {repo_url} удален."
    
    return f"Репозиторий {repo_url} не найден."
# Функция для вывода всех кастомных репозиториев
def list_custom_repos(ubuntu_codename):
    sources_list_path = f"/srv/chroot/{ubuntu_codename}/etc/apt/sources.list"
    
    with open(sources_list_path, "r") as f:
        sources = f.readlines()
    
    repos = [line for line in sources if line.startswith("deb")]
    
    if not repos:
        return "Нет добавленных кастомных репозиториев."
    
    return "\n".join(repos)
@dp.message(Command("addrepo"))
async def add_repo(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.reply("Использование: /addrepo [версия_ubuntu] [URL_репозитория]")
            return
        
        _, ubuntu_version, repo_url = parts
        if ubuntu_version not in SUPPORTED_UBUNTU_VERSIONS:
            await message.reply(f"Версия Ubuntu {ubuntu_version} не поддерживается.")
            return
        
        ubuntu_codename = SUPPORTED_UBUNTU_VERSIONS[ubuntu_version]
        result = add_custom_repo(ubuntu_codename, repo_url)
        await message.reply(result)
    
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")

@dp.message(Command("delrepo"))
async def del_repo(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.reply("Использование: /delrepo [версия_ubuntu] [URL_репозитория]")
            return
        
        _, ubuntu_version, repo_url = parts
        if ubuntu_version not in SUPPORTED_UBUNTU_VERSIONS:
            await message.reply(f"Версия Ubuntu {ubuntu_version} не поддерживается.")
            return
        
        ubuntu_codename = SUPPORTED_UBUNTU_VERSIONS[ubuntu_version]
        result = remove_custom_repo(ubuntu_codename, repo_url)
        await message.reply(result)
    
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")

@dp.message(Command("listrepos"))
async def list_repos(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            await message.reply("Использование: /listrepos [версия_ubuntu]")
            return
        
        _, ubuntu_version = parts
        if ubuntu_version not in SUPPORTED_UBUNTU_VERSIONS:
            await message.reply(f"Версия Ubuntu {ubuntu_version} не поддерживается.")
            return
        
        ubuntu_codename = SUPPORTED_UBUNTU_VERSIONS[ubuntu_version]
        repos = list_custom_repos(ubuntu_codename)
        await message.reply(repos)
    
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")
@dp.message(Command("clear"))
async def search_package(message: types.Message):
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
        "/getpkg [версия_ubuntu] [пакеты]...  - скачивание пакета для указанной версии Ubuntu.\n"
        "/getdocker [докер образ]  - докер образа.\n"
        "/searchpkg [версия_ubuntu] [пакет] - поиск пакетов в репозитории"
        "/addrepo [версия_ubuntu] [URL_репозитория] - добавление кастомного репозитория в sources.list.\n"
        "/delrepo [версия_ubuntu] [URL_репозитория] - удаление кастомного репозитория из sources.list.\n"
        "/listrepos [версия_ubuntu] - просмотр всех добавленных кастомных репозиториев для указанной версии Ubuntu.\n\n"
        "Пример использования:\n"
        "/addrepo 22.04 http://my.custom.repo/ubuntu - добавление кастомного репозитория.\n"
        "/delrepo 22.04 http://my.custom.repo/ubuntu - удаление кастомного репозитория.\n"
        "/listrepos 22.04 - просмотр репозиториев для Ubuntu 22.04.\n"
        "/clearall - отчистить все \n\n"
        "/clear - отчистить базовую директорию \n\n"
        "Если у вас возникнут вопросы, просто ебитесь сами!"
    )
    await message.reply(help_text)

# Функция для скачивания пакетов внутри chroot
async def download_packages(pkg_names, ubuntu_version, chat_id):
    if ubuntu_version not in SUPPORTED_UBUNTU_VERSIONS:
        return None, f"Версия Ubuntu {ubuntu_version} не поддерживается."

    ubuntu_codename = SUPPORTED_UBUNTU_VERSIONS[ubuntu_version]
    setup_chroot(ubuntu_codename)

    work_dir = os.path.join(BASE_DIR, f"{'_'.join(pkg_names)}_{ubuntu_codename}")
    os.makedirs(work_dir, exist_ok=True)

    archive_path = f"{work_dir}.tar.gz"
    
    if os.path.exists(archive_path):
        return archive_path, None

    # Обновляем сообщение о процессе
    await update_progress(chat_id, "Создание chroot-окружения...")

    # Собираем команду для скачивания нескольких пакетов
    pkg_list = " ".join(pkg_names)
    chroot_cmd = f"chroot /srv/chroot/{ubuntu_codename} apt-get -y install --allow-unauthenticated --download-only {pkg_list}"
    
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

@dp.message(Command("clearall"))
async def search_package(message: types.Message):
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
        args = message.text.split(maxsplit=2)
        
        if len(args) < 3:
            await message.reply("Пожалуйста, укажите ключевое слово для поиска и версию Ubuntu.")
            return
        
        search_term = args[2]
        ubuntu_version = args[1]
        chat_id = message.chat.id  # Получаем ID чата для отправки обновлений

        if ubuntu_version not in SUPPORTED_UBUNTU_VERSIONS:
            await message.reply(f"Версия Ubuntu {ubuntu_version} не поддерживается.")
            return

        ubuntu_codename = SUPPORTED_UBUNTU_VERSIONS[ubuntu_version]
        
        # Убедимся, что chroot окружение настроено
        setup_chroot(ubuntu_codename)

        # Выполнение команды поиска пакета через apt-cache внутри chroot
        chroot_cmd = f"chroot /srv/chroot/{ubuntu_codename} apt search {search_term}"
        result = subprocess.run(chroot_cmd, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            await message.reply(f"Ошибка при поиске пакета: {result.stderr}")
        else:
            # Выводим результаты поиска
            search_results = result.stdout.strip()
            if search_results:
                await message.reply(f"Результаты поиска для '{search_term}' в Ubuntu {ubuntu_version}:\n\n{search_results}")
            else:
                await message.reply(f"Не найдено пакетов, соответствующих '{search_term}' в Ubuntu {ubuntu_version}.")
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")

# Обработчик команды
import subprocess

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

        # Путь для скачивания Docker образа
        download_dir = f"/tmp/{docker_image}"

        # Убедимся, что директория для Docker образа существует
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)

        # Скачиваем образ с помощью skopeo
        #skopeo_cmd = f"skopeo copy docker://docker.io/library/{docker_image} dir:{download_dir}"
        filename=str(docker_image)
        filename=filename.replace("/", "_").replace(":", "_")+ ".tar"
        skopeo_cmd = f"skopeo copy docker://{docker_image} docker-archive:{BASE_DIR}/{filename}"
        result = subprocess.run(skopeo_cmd, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            await message.reply(f"Ошибка при скачивании Docker образа: {result.stderr}")
            return

        # Архивируем скачанный Docker образ
        #tar_cmd = f"tar -cvf {BASE_DIR}/{docker_image}.tar -C /tmp {docker_image}"
        
        #result = subprocess.run(tar_cmd, shell=True, capture_output=True, text=True)

        # if result.returncode != 0:
        #     await message.reply(f"Ошибка при упаковке Docker образа в tar архив: {result.stderr}")
        #     return
        #shutil.rmtree(f"/tmp/{docker_image}")
        # Уведомляем пользователя о завершении процесса
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
        _, ubuntu_version, *pkg_names = message.text.split()
        chat_id = message.chat.id  # Получаем ID чата для отправки обновлений
        
        if not pkg_names:
            await message.reply("Пожалуйста, укажите хотя бы один пакет для скачивания.")
            return

        # Скачиваем несколько пакетов и создаем архив
        archive_path, error = await download_packages(pkg_names, ubuntu_version, chat_id)
        
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
