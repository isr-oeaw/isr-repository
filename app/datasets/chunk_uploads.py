import json
import os
import re
import shutil
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.utils import timezone

CHUNK_ROOT = 'tmp/chunks'
CHUNK_MAX_AGE_HOURS = 24
UPLOAD_ID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)


def chunk_base_dir(user_id, upload_id):
    return Path(settings.MEDIA_ROOT) / CHUNK_ROOT / str(user_id) / str(upload_id)


def meta_path(user_id, upload_id):
    return chunk_base_dir(user_id, upload_id) / 'meta.json'


def assembled_file_path(user_id, upload_id, file_index):
    return chunk_base_dir(user_id, upload_id) / str(file_index)


def validate_upload_id(upload_id):
    if not upload_id or not UPLOAD_ID_PATTERN.match(str(upload_id)):
        raise ValueError('Invalid upload_id.')
    return str(upload_id)


def cleanup_old_chunk_dirs():
    """Remove chunk upload directories older than CHUNK_MAX_AGE_HOURS."""
    root = Path(settings.MEDIA_ROOT) / CHUNK_ROOT
    if not root.exists():
        return

    cutoff = timezone.now() - timedelta(hours=CHUNK_MAX_AGE_HOURS)
    for user_dir in root.iterdir():
        if not user_dir.is_dir():
            continue
        for upload_dir in user_dir.iterdir():
            if not upload_dir.is_dir():
                continue
            try:
                from datetime import datetime

                mtime = datetime.fromtimestamp(
                    upload_dir.stat().st_mtime,
                    tz=timezone.get_current_timezone(),
                )
            except OSError:
                continue
            if mtime < cutoff:
                shutil.rmtree(upload_dir, ignore_errors=True)


def _load_meta(user_id, upload_id):
    path = meta_path(user_id, upload_id)
    if not path.exists():
        return {'files': {}}
    with path.open('r', encoding='utf-8') as handle:
        return json.load(handle)


def _save_meta(user_id, upload_id, meta):
    base = chunk_base_dir(user_id, upload_id)
    base.mkdir(parents=True, exist_ok=True)
    with meta_path(user_id, upload_id).open('w', encoding='utf-8') as handle:
        json.dump(meta, handle)


def append_chunk(user, upload_id, file_index, chunk_index, total_chunks, filename, chunk_file):
    """Append one chunk to an in-progress upload. Chunks must arrive in order."""
    upload_id = validate_upload_id(upload_id)
    cleanup_old_chunk_dirs()

    file_index = int(file_index)
    chunk_index = int(chunk_index)
    total_chunks = int(total_chunks)

    if total_chunks < 1:
        raise ValueError('total_chunks must be at least 1.')
    if chunk_index < 0 or chunk_index >= total_chunks:
        raise ValueError('chunk_index out of range.')

    chunk_bytes = chunk_file.read()
    chunk_size = len(chunk_bytes)
    if chunk_size > settings.MAX_DATASET_UPLOAD_SIZE:
        raise ValueError('Chunk exceeds maximum upload size.')

    meta = _load_meta(user.pk, upload_id)
    files_meta = meta.setdefault('files', {})
    file_key = str(file_index)
    file_meta = files_meta.get(file_key, {
        'filename': filename,
        'total_chunks': total_chunks,
        'next_chunk_index': 0,
        'size': 0,
    })

    if file_meta['total_chunks'] != total_chunks:
        raise ValueError('total_chunks mismatch for file.')
    if file_meta['filename'] != filename:
        raise ValueError('filename mismatch for file.')
    if file_meta['next_chunk_index'] != chunk_index:
        raise ValueError(
            f'Expected chunk {file_meta["next_chunk_index"]}, received {chunk_index}.'
        )

    dest_path = assembled_file_path(user.pk, upload_id, file_index)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    mode = 'ab' if dest_path.exists() else 'wb'
    with dest_path.open(mode) as handle:
        handle.write(chunk_bytes)

    file_meta['size'] += chunk_size
    file_meta['next_chunk_index'] = chunk_index + 1
    files_meta[file_key] = file_meta
    meta['files'] = files_meta
    _save_meta(user.pk, upload_id, meta)

    return {
        'upload_id': upload_id,
        'file_index': file_index,
        'chunk_index': chunk_index,
        'received_chunks': file_meta['next_chunk_index'],
        'total_chunks': total_chunks,
        'assembled_size': file_meta['size'],
    }


def load_assembled_upload_files(user, upload_id, expected_files):
    """
    Validate assembled chunk files and return Django File objects ready for saving.

    expected_files: list of dicts with file_index, filename, file_size (int).
    """
    upload_id = validate_upload_id(upload_id)
    if not expected_files:
        raise ValueError('No chunked files specified.')

    meta = _load_meta(user.pk, upload_id)
    files_meta = meta.get('files', {})
    total_size = 0
    opened_files = []

    for entry in expected_files:
        file_index = int(entry['file_index'])
        filename = entry['filename']
        expected_size = int(entry['file_size'])
        file_key = str(file_index)

        if file_key not in files_meta:
            raise ValueError(f'File index {file_index} was not uploaded.')

        file_meta = files_meta[file_key]
        if file_meta['next_chunk_index'] != file_meta['total_chunks']:
            raise ValueError(f'File "{filename}" upload is incomplete.')
        if file_meta['filename'] != filename:
            raise ValueError(f'Filename mismatch for file index {file_index}.')
        if file_meta['size'] != expected_size:
            raise ValueError(
                f'Size mismatch for "{filename}": expected {expected_size}, '
                f'got {file_meta["size"]}.'
            )

        path = assembled_file_path(user.pk, upload_id, file_index)
        if not path.exists():
            raise ValueError(f'Assembled file missing for index {file_index}.')

        if expected_size > settings.MAX_DATASET_UPLOAD_SIZE:
            raise ValueError(f'File "{filename}" exceeds maximum upload size.')

        total_size += expected_size
        django_file = File(path.open('rb'), name=os.path.basename(filename))
        django_file.size = expected_size
        opened_files.append(django_file)

    if total_size > settings.MAX_DATASET_UPLOAD_SIZE:
        for handle in opened_files:
            handle.close()
        raise ValueError('Total upload size exceeds the maximum allowed limit.')

    return opened_files, total_size


def remove_chunk_upload(user_id, upload_id):
    """Delete temporary chunk directory after successful version creation."""
    upload_id = validate_upload_id(upload_id)
    base = chunk_base_dir(user_id, upload_id)
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
