from app.minio import delete_file as delete
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

scheduler = BackgroundScheduler()


async def schedule_file_deletion(db, file_obj, filename):
    def delete_file():
        try:
            db.delete(file_obj)
            db.commit()
            # Delete the file from storage minIO
            delete(file_obj)

            print(f"Deleted file record from database: {filename}")
        except Exception as e:
            print(f"Error occurred during file deletion: {e}")

    date = datetime.now() + timedelta(seconds=15)
    job = scheduler.add_job(delete_file, "date", run_date=date)

    print("Job has been scheduled successfully")

    return job.id
