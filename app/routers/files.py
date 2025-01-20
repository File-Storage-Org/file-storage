import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from starlette import status
from minio.error import S3Error, ServerError

from app.cron import scheduler, schedule_file_deletion
from app.database import SessionLocal
from app import models
from app.deps import is_token_expired
from app.schemas import File, Favorite, FileID, FilesFavorite, Files
from app.perms.isAuthenticated import is_authenticated
from app.services.minio import upload_file as upload_to_minio_s3, delete_file as delete_file_from_minio_s3
from app.services.text_extractor import TextExtractor
from app.services.pinecone_serv import PineconeService

SUPPORTIVE_DOC_TYPES = [".docx", ".pptx", ".txt", ".pdf"]

router = APIRouter()
pc = PineconeService()
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
        db: Session = Depends(get_db),
        user_id: int | None = Depends(is_authenticated)
):
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    files = (
        db.query(models.File, models.Favorite.id)
        .filter(
            models.File.user_id == user_id,
            models.File.should_delete.is_(False)
        )
        .join(models.Favorite, isouter=True)
        .order_by(models.File.created_at.desc())
        .all()
    )

    return [{"data": file, "fav": fav_id} for file, fav_id in files]


@router.get(
    "/favorites",
    dependencies=[Depends(is_token_expired)],
    summary="Get all fav files",
    response_model=list[FilesFavorite],
)
async def get_all_favorites(
        db: Session = Depends(get_db),
        user_id: int | None = Depends(is_authenticated)
):
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    files = (
        db.query(models.File, models.Favorite.id)
        .filter(
            models.File.user_id == user_id,
            models.File.should_delete.is_(False)
        )
        .join(models.File.favorites)
        .all()
    )

    return [{"data": file, "fav": fav_id} for file, fav_id in files]


@router.get(
    "/deleted",
    dependencies=[Depends(is_token_expired)],
    summary="Get all deleted files",
    response_model=list[Files],
)
async def get_all_deleted(
        db: Session = Depends(get_db),
        user_id: int | None = Depends(is_authenticated)
):
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    files = (
        db.query(models.File)
        .filter(
            models.File.user_id == user_id,
            models.File.should_delete.is_(True)
        )
        .all()
    )

    return [{"data": file} for file in files]


@router.get(
    "/search",
    dependencies=[Depends(is_token_expired)],
    summary="Get all matchup files",
    response_model=list[FilesFavorite],
)
async def get_all_search_matchups(
        q: str,
        db: Session = Depends(get_db),
        user_id: int | None = Depends(is_authenticated)
):
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if not q:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query is empty!")

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

    return [{"data": file, "fav": fav_id} for file, fav_id in files]


@router.get(
    "/ai-search",
    dependencies=[Depends(is_token_expired)],
    summary="Get all AI matchup files",
    response_model=list[FilesFavorite],
)
async def get_all_ai_matchup_files(
        q: str,
        db: Session = Depends(get_db),
        user_id: int | None = Depends(is_authenticated)
):
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if not q:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query is empty!")
    
    try:
        matched_embeddings = pc.get_matched_embeddings(query=q)["matches"]
        file_ids: list[int] = []
        if len(matched_embeddings):
            for file in matched_embeddings:
                # file["score"] is accurate percentage of the answer
                file_ids.append(int(file["metadata"]["doc_id"]))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error in receiving mathchings - {e}"
        )

    files = (
        db.query(models.File, models.Favorite.id)
        .filter(
            models.File.user_id == user_id,
            models.File.should_delete.is_(False),
            models.File.id.in_(set(file_ids)),
        )
        .join(models.Favorite, isouter=True)
        .order_by(models.File.created_at.desc())
        .all()
    )

    return [{"data": file, "fav": fav_id} for file, fav_id in files]


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
    dependencies=[Depends(is_token_expired)],
    summary="Create file",
    response_model=File,
)
async def upload_file(
    file: UploadFile,
    user_id: Annotated[str, Depends(is_authenticated)],
    db: Session = Depends(get_db),
):
    try:
        file_name, file_ext = os.path.splitext(file.filename)
        file_content = await file.read()
        if not file_ext:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Your file doesn't have an extension, please edit it."
            )

        # Upload the file to storage minIO
        try:
            file_url = await upload_to_minio_s3(file_content, file.filename)
        except S3Error as s3_error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"S3 Error - {str(s3_error)}"
            )
        except ServerError as serv_error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"MinIO Server Error - {str(serv_error)}"
            )

        # Add file to PostgreSQL
        with db.begin():
            db_file = models.File(
                name=file_name,
                file=file_url,
                user_id=int(user_id),
                format=file_ext,
            )
            db.add(db_file)
            db.flush() # add db_file.id to instance

            if file_ext in SUPPORTIVE_DOC_TYPES:
                # Add file to Pinecone
                try:
                    text = TextExtractor(file=file_content, file_ext=file_ext).extract()
                    print(text)
                    pc.upload_embeddings(text, str(db_file.id))
                except Exception as e:
                    # TODO: find a list of pinecone exceptions
                    db.rollback()
                    delete_file_from_minio_s3(db_file)
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

        return db_file
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


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

        job_id = await schedule_file_deletion(db, file_to_delete)
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
