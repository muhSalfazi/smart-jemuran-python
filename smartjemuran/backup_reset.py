import os
from datetime import datetime
import subprocess
from django.conf import settings
from django.core.management import call_command
from smartjemuran.models import JemuranData


def backup_and_reset():
    # 1. Backup data ke SQL/Excel
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    backup_filename = f"jemuran_backup_{timestamp}.sql"

    # Backup MySQL (gunakan mysqldump)
    db_name = settings.DATABASES['default']['NAME']
    db_user = settings.DATABASES['default']['USER']
    db_pass = settings.DATABASES['default']['PASSWORD']

    os.makedirs("backups", exist_ok=True)
    backup_path = f"backups/{backup_filename}"

    # Jalankan mysqldump (pastikan sudah terinstall di sistem)
    subprocess.run(
        f"mysqldump -u {db_user} -p{db_pass} {db_name} > {backup_path}",
        shell=True,
        check=True
    )

    # (Opsional) Backup ke Excel
    import pandas as pd
    data = JemuranData.objects.all().values()
    df = pd.DataFrame(data)
    df.to_excel(f"backups/jemuran_data_{timestamp}.xlsx", index=False)

    # 2. Reset database (hapus semua data)
    JemuranData.objects.all().delete()
    print("Database reset selesai. Data lama telah di-backup.")

    # 3. (Opsional) Upload ke Google Drive
    # Gunakan solusi dari contoh sebelumnya (gdrive/rclone)


if __name__ == "__main__":
    backup_and_reset()
