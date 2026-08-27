import os
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.voice_interview.schemas import AuthenticateRequest
from app.modules.voice_interview.repositories.interview_repository import InterviewRepository
from app.modules.voice_interview.repositories.access_repository import AccessRepository
from app.modules.voice_interview.services.link_generator import LinkGenerator
from app.modules.voice_interview.services.interview_service import VoiceInterviewService
from app.modules.voice_interview.services.question_generator import VoiceQuestionGenerator
from app.modules.voice_interview.services.stt_service import get_stt_provider
from app.modules.voice_interview.services.tts_service import get_tts_provider
from app.modules.voice_interview.services.answer_evaluator import get_answer_evaluator

router = APIRouter()

question_gen = VoiceQuestionGenerator()
stt = get_stt_provider()
tts = get_tts_provider()
evaluator = get_answer_evaluator()

AUDIO_DIR = "audio_files/voice_interview"
os.makedirs(AUDIO_DIR, exist_ok=True)


@router.get("/ping")
def ping():
    return {"module": "voice_interview", "status": "ok"}


@router.post("/candidates/{candidate_id}/provision")
def provision_candidate(candidate_id: UUID, db: Session = Depends(get_db)):
    link_gen = LinkGenerator(AccessRepository(db))
    link_gen.create_link(candidate_id)
    return {"status": "provisioned"}


@router.post("/authenticate")
def authenticate(payload: AuthenticateRequest, db: Session = Depends(get_db)):
    link_gen = LinkGenerator(AccessRepository(db))
    access, error = link_gen.authenticate(payload.token, payload.access_code, payload.candidate_id)
    if error:
        raise HTTPException(401, error)

    interview_repo = InterviewRepository(db)
    session = interview_repo.create_session(access.candidate_id)
    AccessRepository(db).mark_used(access, session.id)

    question = question_gen.get_question(0)
    return {
        "interview_id": session.id,
        "question_index": 0,
        "question": question,
        "total_questions": question_gen.get_total(),
    }


@router.get("/{interview_id}/next-question")
def next_question(interview_id: UUID, from_index: int, db: Session = Depends(get_db)):
    interview_repo = InterviewRepository(db)
    session = interview_repo.get_session(interview_id)
    if not session:
        raise HTTPException(404, "Interview not found")

    if from_index != session.current_question_index:
        question = question_gen.get_question(session.current_question_index)
        if question is None:
            return {"status": "completed", "overall_score": session.overall_score}
        return {"question_index": session.current_question_index, "question": question}

    session.current_question_index += 1
    question = question_gen.get_question(session.current_question_index)

    if question is None:
        interview_repo.complete_session(session)
        return {"status": "completed", "overall_score": session.overall_score}

    interview_repo.save(session)
    return {"question_index": session.current_question_index, "question": question}


@router.get("/{interview_id}/questions/{index}/audio")
def question_audio(interview_id: UUID, index: int):
    question = question_gen.get_question(index)
    if question is None:
        raise HTTPException(404, "No question at that index")

    output_path = f"{AUDIO_DIR}/q_{index}.wav"
    if not os.path.exists(output_path):
        tts.speak(question, output_path)

    return FileResponse(output_path, media_type="audio/wav")


@router.post("/{interview_id}/questions/{index}/answer")
async def submit_answer(
    interview_id: UUID,
    index: int,
    audio: UploadFile,
    start_ts: float = Form(...),
    end_ts: float = Form(...),
    db: Session = Depends(get_db),
):
    question = question_gen.get_question(index)
    if question is None:
        raise HTTPException(404, "No question at that index")

    answer_dir = f"{AUDIO_DIR}/{interview_id}"
    os.makedirs(answer_dir, exist_ok=True)
    audio_path = f"{answer_dir}/q_{index}.webm"

    audio_bytes = await audio.read()
    if len(audio_bytes) < 1000:
        raise HTTPException(400, "Recording was empty or too short")

    with open(audio_path, "wb") as f:
        f.write(audio_bytes)

    try:
        transcript = stt.transcribe(audio_path)
    except Exception as e:
        print(f"STT failed for {interview_id}/{index}: {e}")
        raise HTTPException(502, "Transcription service is unavailable. Please retry.")

    try:
        scores = evaluator.evaluate(question, transcript, start_ts, end_ts)
    except Exception as e:
        print(f"Scoring failed for {interview_id}/{index}: {e}")
        scores = {
            "relevance": None, "content_depth": None, "structure_clarity": None,
            "fluency": None, "pacing_wpm": None, "composite": None,
            "feedback": "Scoring unavailable for this answer.",
        }

    InterviewRepository(db).save_answer(
        interview_id, index, question, audio_path, transcript, start_ts, end_ts, scores
    )
    return {"transcript": transcript}


@router.get("/{interview_id}/full")
def get_full_interview(interview_id: UUID, db: Session = Depends(get_db)):
    result = VoiceInterviewService(db).get_results(interview_id)
    if result is None:
        raise HTTPException(404, "Interview not found")
    return result