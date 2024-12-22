from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from starlette import status

from app.cron import scheduler, schedule_file_deletion
from app.database import SessionLocal
from app import models
from app.deps import is_token_expired
from app.schemas import File, Favorite, FileID, FilesFavorite, Files
from app.perms.isAuthenticated import is_authenticated
from app.minio import upload_file as upload, remove_extension

router = APIRouter()
scheduler.start()


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/connection")
async def connection():
    return "OK"


@router.get(
    "/files",
    dependencies=[Depends(is_token_expired)],
    summary="Get all files",
    response_model=list[FilesFavorite],
)
async def get_all_files(
        q: str | None = None,
        db: Session = Depends(get_db),
        user_id: int | None = Depends(is_authenticated)
):
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if q:
        files = (
            db.query(models.File, models.Favorite.id)
            .filter(
                models.File.user_id == user_id,
                models.File.should_delete.is_(False),
                func.lower(models.File.name).contains(q),
            )
            .join(models.Favorite, isouter=True)
            .order_by(models.File.created_at.desc())
            .all()
        )
    else:
        files = (
            db.query(models.File, models.Favorite.id)
            .filter(
                models.File.user_id == user_id,
                models.File.should_delete.is_(False),
            )
            .join(models.Favorite, isouter=True)
            .order_by(models.File.created_at.desc())
            .all()
        )

    result = [{"data": file, "fav": fav_id} for file, fav_id in files]

    return result


@router.get(
    "/favorites",
    dependencies=[Depends(is_token_expired)],
    summary="Get all favorites files",
    response_model=list[FilesFavorite],
)
async def get_all_favorites(
        q: str | None = None,
        db: Session = Depends(get_db),
        user_id: int | None = Depends(is_authenticated)
):
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if q:
        files = (
            db.query(models.File, models.Favorite.id)
            .filter(
                models.File.user_id == user_id,
                models.File.should_delete.is_(False),
                func.lower(models.File.name).contains(q),
            )
            .join(models.File.favorites)
            .all()
        )
    else:
        files = (
            db.query(models.File, models.Favorite.id)
            .filter(
                models.File.user_id == user_id,
                models.File.should_delete.is_(False),
            )
            .join(models.File.favorites)
            .all()
        )

    result = [{"data": file, "fav": fav_id} for file, fav_id in files]

    return result


@router.get(
    "/deleted",
    dependencies=[Depends(is_token_expired)],
    summary="Get all deleted files",
    response_model=list[Files],
)
async def get_all_deleted(
        q: str | None = None,
        db: Session = Depends(get_db),
        user_id: int | None = Depends(is_authenticated)
):
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if q:
        files = (
            db.query(models.File)
            .filter(
                models.File.user_id == user_id,
                models.File.should_delete.is_(True),
                func.lower(models.File.name).contains(q),
            )
            .all()
        )
    else:
        files = (
            db.query(models.File)
            .filter(
                models.File.user_id == user_id,
                models.File.should_delete.is_(True),
            )
            .all()
        )

    return [{"data": file} for file in files]


@router.get(
    "/file/{file_id}",
    dependencies=[Depends(is_token_expired), Depends(is_authenticated)],
    summary="Get file",
    response_model=File,
)
async def get_file(file_id: int, db: Session = Depends(get_db)):
    file = db.query(models.File).filter_by(id=file_id).first()

    return file


@router.post(
    "/file/upload",
    dependencies=[Depends(is_token_expired), Depends(is_authenticated)],
    summary="Create file",
    response_model=File,
)
async def upload_file(
    file: UploadFile,
    user_id: Annotated[str, Depends(is_authenticated)],
    db: Session = Depends(get_db),
):
    extension = file.headers.get("content-type").split("/")[1]
    # Upload the file to storage minIO
    file_url, file_uuid = await upload(file, extension)

    filename = remove_extension(file.filename)

    db_file = models.File(
        name=filename,
        file=file_url,
        file_uuid=file_uuid,
        user_id=int(user_id),
        format=extension,
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    uploaded_file = db.query(models.File).filter_by(id=db_file.id).first()

    return uploaded_file


@router.delete(
    "/file/{file_id}",
    dependencies=[Depends(is_token_expired), Depends(is_authenticated)],
    summary="Delete file",
    response_model=File,
)
async def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
):
    if file_id:
        file_to_delete = db.query(models.File).filter_by(id=file_id).first()
        if not file_to_delete:
            raise HTTPException(status_code=404, detail="File not found")

        file_to_delete.should_delete = True
        db.commit()
        db.refresh(file_to_delete)

        job_id = await schedule_file_deletion(db, file_to_delete, file_to_delete.name)
        job_instance = models.ScheduledJob(file_id=file_id, job_id=job_id)
        db.add(job_instance)
        db.commit()

    else:
        raise HTTPException(status_code=400, detail="file_id is None")

    return file_to_delete


@router.patch(
    "/file-restore/{file_id}",
    dependencies=[Depends(is_token_expired), Depends(is_authenticated)],
    summary="Restore file",
    response_model=File,
)
async def restore_file(
    file_id: int,
    db: Session = Depends(get_db),
):
    if file_id:
        file_to_restore = db.query(models.File).filter_by(id=file_id).first()
        if not file_to_restore:
            raise HTTPException(status_code=404, detail="File not found")

        file_to_restore.should_delete = False
        db.commit()
        db.refresh(file_to_restore)

        # running_jobs = scheduler.get_jobs()
        # job_lst = []
        # for job in running_jobs:
        #     job_lst.append(job.id)

        # Terminate and delete deleting file cron job
        cron = db.query(models.ScheduledJob).filter_by(file_id=file_id).first()
        if cron:
            scheduler.remove_job(str(cron.job_id).replace("-", ""))

            print("Job has been removed successfully")

            db.delete(cron)
            db.commit()
        else:
            raise HTTPException(status_code=404, detail="Cron not found")

    else:
        raise HTTPException(status_code=400, detail="file_id is None")

    return file_to_restore


@router.post(
    "/favorites/add",
    dependencies=[Depends(is_token_expired), Depends(is_authenticated)],
    summary="Add file to fav",
    response_model=Favorite,
)
async def add_to_favorites(
    file: FileID,
    user_id: Annotated[str, Depends(is_authenticated)],
    db: Session = Depends(get_db),
):
    if file:
        db_file = db.query(models.File).filter_by(id=file.file_id).first()
        if not db_file:
            raise HTTPException(status_code=404, detail="File not found")

        is_fav = db.query(models.Favorite).filter_by(file_id=file.file_id).first()

        if is_fav:
            db.delete(is_fav)
            db.commit()

            return Favorite(
                id=is_fav.id, file_id=is_fav.file_id, user_id=is_fav.user_id
            )

        favorite = models.Favorite(user_id=int(user_id), file_id=file.file_id)
        db.add(favorite)
        db.commit()
        db.refresh(favorite)
    else:
        raise HTTPException(status_code=400, detail="file_id is None")

    return favorite
