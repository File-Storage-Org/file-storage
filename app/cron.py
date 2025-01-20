from app.services.minio import delete_file as delete_from_minio_s3
from sqlalchemy.orm import Session
from app.schemas import File
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

scheduler = BackgroundScheduler()


async def schedule_file_deletion(db: Session, file: File):
    def delete_file():
        try:
            db.delete(file)
            db.commit()
            # Delete the file from storage minIO
            delete_from_minio_s3(file)

            print(f"Deleted file record from database: {file.name}")
        except Exception as e:
            print(f"Error occurred during file deletion: {e}")

    date = datetime.now() + timedelta(seconds=30)
    job = scheduler.add_job(delete_file, "date", run_date=date)

    print("Job has been scheduled successfully")

    return job.id
