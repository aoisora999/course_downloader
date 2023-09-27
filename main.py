import os
import re
import asyncio
import patoolib
import shutil
import speedtest
from pyrogram import Client, filters
from moviepy.editor import VideoFileClip
from config import *


app = Client(
    "file_downloader_bot",
    api_id=api_id,
    api_hash=api_hash,
    bot_token=bot_token
)

DOWNLOAD_FOLDER = "download/"
if not os.path.exists(DOWNLOAD_FOLDER):
    os.mkdir(DOWNLOAD_FOLDER)

VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.flv']
all_links = []
user_actions = {}
doc_list = []


def get_speedtest_results():
    speed = speedtest.Speedtest()
    download_speed = speed.download() / 10**6  # Convert from bits per second to Mbps
    upload_speed = speed.upload() / 10**6      # Convert from bits per second to Mbps
    ping = speed.results.ping
    return (
        f"<b>Download Speed:</b> {download_speed:.2f} Mbps\n\n"
        f"<b>Upload Speed:</b> {upload_speed:.2f} Mbps\n\n"
        f"<b>Ping:</b> {ping} ms"
    )


def unzip_file(archive_path, output_folder):
    """Unarchive a file."""
    patoolib.extract_archive(archive_path, outdir=output_folder)


async def get_video_thumbnail(video_path, output_path, duration):
    """Extract a thumbnail from a video."""
    with VideoFileClip(video_path) as clip:
        # Extract thumbnail 1/4 into the video's duration
        thumbnail_time = duration / 4
        clip.save_frame(output_path, t=thumbnail_time)
    return output_path


async def send_progress_upload(current, total, message, last_update_time, progress_message):
    if (asyncio.get_running_loop().time() - last_update_time[0]) > 5:  # 5 seconds
        percent = (current * 100) / total
        await progress_message.edit_text(f"Upload progress: {percent:.2f}%")
        last_update_time[0] = asyncio.get_running_loop().time()


async def send_videos_from_folder(folder_path, chat_id, message):
    """Send files from a folder to a specified chat."""
    global all_links
    all_files = []

    for root, _, files in os.walk(folder_path):
        for file in files:
            all_files.append((file, os.path.join(root, file)))

    def extract_prefix(filename):
        match = re.match(r"(\d+)", filename)
        return int(match.group(1)) if match else 99999

    sorted_files = sorted(all_files, key=lambda x: extract_prefix(x[0]))

    for file, file_path in sorted_files:
        sent_message = None
        if file.endswith('.srt'):
            continue

        if any(file.endswith(ext) for ext in VIDEO_EXTENSIONS):  # If it's a video
            with VideoFileClip(file_path) as clip:
                duration = int(clip.duration)
                width, height = clip.size

            thumbnail_path = os.path.splitext(file_path)[0] + "_thumbnail.jpg"
            await get_video_thumbnail(file_path, thumbnail_path, duration)

            caption = os.path.splitext(file)[0]
            logo = f"<b>{caption}\n\n<a href='tg://user?id=6190014678'>Yami Code Academy</a></b>"

            upload_progress_message = await app.send_message(chat_id, "Upload progress: 0%")
            last_update_time = [asyncio.get_running_loop().time()]

            sent_message = await app.send_video(
                chat_id=chat_id,
                video=file_path,
                duration=duration,
                width=width,
                height=height,
                thumb=thumbnail_path,
                caption=logo,
                supports_streaming=True,
                disable_notification=True,
                progress=send_progress_upload,
                progress_args=(message, last_update_time, upload_progress_message)
            )
            await upload_progress_message.delete()
            os.remove(thumbnail_path)
        else:  # If it's a non-video file
            caption = os.path.splitext(file)[0]
            sent_message = await app.send_document(
                chat_id=chat_id,
                document=file_path,
                disable_notification=True
            )

        # After sending, get the message link and send to the user
        if sent_message:
            file_link = f"https://t.me/c/{str(chat_id)[4:]}/{sent_message.id}"
            hyper_text = f"<b><a href={file_link}>{caption}</a></b>"
            all_links.append(hyper_text)

        await asyncio.sleep(6)

    all_links_text = "\n".join(all_links)
    await app.send_message(chat_id, all_links_text)
    all_links = []
    noti_text = await app.send_message(chat_id, "Done Uploading for this zip")
    await asyncio.sleep(2)
    await noti_text.delete()
    shutil.rmtree(folder_path)


async def send_progress(current, total, message, last_update_time, progress_message):
    if (asyncio.get_running_loop().time() - last_update_time[0]) > 5:  # 5 seconds
        percent = (current * 100) / total
        await progress_message.edit_text(f"Download progress: {percent:.2f}%")
        last_update_time[0] = asyncio.get_running_loop().time()


@app.on_message(filters.command("start"))
async def get_doc(client, message):
    user_actions[message.chat.id] = {}
    user_actions[message.chat.id]["user_adding"] = True
    await message.delete()
    noti_text = await message.reply_text("Start sending doc...")
    await asyncio.sleep(1)
    await noti_text.delete()


@app.on_message(filters.document)
async def save_doc(client, message):
    chat_id = message.chat.id
    file_name = message.document.file_name
    temp_dict = {
        "file_name": file_name,
        "chat_id": chat_id,
        "message": message
    }
    doc_list.append(temp_dict)
    await message.delete()
    noti_text = await message.reply_text("saved doc")
    await asyncio.sleep(1)
    await noti_text.delete()


@app.on_message(filters.command("stop"))
async def stop_doc(client, message):
    global doc_list
    if message.chat.id not in user_actions:
        return
    user_actions.pop(message.chat.id)
    await message.delete()
    noti_text = await message.reply_text("stopped")
    await asyncio.sleep(1)
    await noti_text.delete()
    if doc_list:
        for doc in doc_list:
            file_name = doc["file_name"]
            chat_id = doc["chat_id"]
            message = doc["message"]
            base_filename = os.path.splitext(file_name)[0]
            sent_message = await client.send_message(message.chat.id, f".\n\n<b>{base_filename}</b>\n\n.")
            base_file_link = f"https://t.me/c/{str(chat_id)[4:]}/{sent_message.id}"
            hyper_text = f"<b><a href={base_file_link}>{base_filename}</a></b>\n"
            all_links.append(hyper_text)
            download_path = os.path.join(DOWNLOAD_FOLDER, file_name)

            progress_message = await message.reply_text("Download progress: 0%")
            last_update_time = [asyncio.get_running_loop().time()]  # Use a list to make it mutable

            await message.download(
                file_name=download_path,
                progress=send_progress,
                progress_args=(message, last_update_time, progress_message)
            )
            await progress_message.delete()

            # Check if the downloaded file is a zip file and unzip it if it is
            if file_name.endswith('.zip') or file_name.endswith('.rar'):
                unzip_file(download_path, DOWNLOAD_FOLDER)
                status_t = await message.reply_text("The ZIP file has been unzipped!")
                await asyncio.sleep(0.5)
                await status_t.delete()
                # Send videos from the unzipped folder
                await send_videos_from_folder(DOWNLOAD_FOLDER, chat_id, message)
            else:
                await progress_message.edit_text(f"File has been downloaded and saved as {download_path}!")

    doc_list = []


@app.on_message(filters.command("speedtest"))
async def handle_speedtest(client, message):
    result_text = "Running speed test..."
    status_message = await message.reply_text(result_text)

    # Run the speed test
    results = get_speedtest_results()

    # Update the status message with the results
    await status_message.edit_text(results)


if __name__ == "__main__":
    print("Bot Started!")
    app.run()
