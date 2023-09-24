import os
import re
import asyncio
import zipfile
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


def unzip_file(zip_path, output_folder):
    """Unzip a zip file."""
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(output_folder)
    os.remove(zip_path)  # Delete the original .zip file after unzipping


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
    """Send video files from a folder to a specified chat."""
    video_files = []

    for root, _, files in os.walk(folder_path):
        for file in files:
            if any(file.endswith(ext) for ext in VIDEO_EXTENSIONS):
                video_files.append((file, os.path.join(root, file)))

    # Extract and sort the video files based on the numeric prefix
    def extract_prefix(filename):
        match = re.match(r"(\d+)", filename)
        return int(match.group(1)) if match else 99999

    sorted_video_files = sorted(video_files, key=lambda x: extract_prefix(x[0]))

    # Rename files to adjust the bullet number, while keeping the rest of the name unchanged
    for idx, (file, video_path) in enumerate(sorted_video_files, 1):
        bullet_number, rest_of_name = re.match(r"(\d+)\. (.+)", file).groups()
        new_name = f"{idx}. {rest_of_name}"
        new_path = os.path.join(root, new_name)
        os.rename(video_path, new_path)
        sorted_video_files[idx-1] = (new_name, new_path)

    for file, video_path in sorted_video_files:
        # Extract video metadata
        with VideoFileClip(video_path) as clip:
            duration = int(clip.duration)
            width, height = clip.size

        thumbnail_path = os.path.splitext(video_path)[0] + "_thumbnail.jpg"
        await get_video_thumbnail(video_path, thumbnail_path, duration)

        # Extract the video name without its extension for the caption
        caption = os.path.splitext(file)[0]
        logo = f"<b>{caption}\n\n<a href='tg://user?id=6190014678'>Yami Code Academy</a></b>"

        upload_progress_message = await app.send_message(chat_id, "Upload progress: 0%")
        last_update_time = [asyncio.get_running_loop().time()]  # Use a list to make it mutable

        await app.send_video(
            chat_id=chat_id,
            video=video_path,
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
        # Optional: Delete the thumbnail after sending
        os.remove(thumbnail_path)

    # Delete the folder after sending all videos
    shutil.rmtree(folder_path)


async def send_progress(current, total, message, last_update_time, progress_message):
    if (asyncio.get_running_loop().time() - last_update_time[0]) > 5:  # 5 seconds
        percent = (current * 100) / total
        await progress_message.edit_text(f"Download progress: {percent:.2f}%")
        last_update_time[0] = asyncio.get_running_loop().time()


@app.on_message(filters.document)
async def download_file(client, message):
    file_name = message.document.file_name
    base_filename = os.path.splitext(file_name)[0]
    await client.send_message(message.chat.id, f".\n\n<b>{base_filename}</b>\n\n.")
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
    if file_name.endswith('.zip'):
        unzip_file(download_path, DOWNLOAD_FOLDER)
        status_t = await message.reply_text("The ZIP file has been unzipped!")
        await asyncio.sleep(0.5)
        await status_t.delete()
        # Send videos from the unzipped folder
        await send_videos_from_folder(DOWNLOAD_FOLDER, message.chat.id, message)
    else:
        await progress_message.edit_text(f"File has been downloaded and saved as {download_path}!")


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
