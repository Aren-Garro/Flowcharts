"""Async rendering task manager for non-blocking flowchart generation.

Phase 4: Background rendering jobs so the web UI doesn't block on
long-running Graphviz/D2/Kroki renders. Uses threading for simplicity
(no Celery needed). Jobs are stored in-memory with TTL expiration.
"""

import uuid
import time
import logging
import threading
from typing import Optional, Dict
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)
TMP_ROOT = Path.cwd() / '.tmp' / 'web' / 'async'
TMP_ROOT.mkdir(parents=True, exist_ok=True)


class JobStatus(str, Enum):
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'


@dataclass
class RenderJob:
    """A background rendering job."""
    id: str
    status: JobStatus = JobStatus.PENDING
    renderer: str = 'mermaid'
    format: str = 'png'
    output_path: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    progress_pct: int = 0
    progress_msg: str = ''

    @property
    def elapsed(self) -> float:
        if self.started_at:
            end = self.completed_at or time.time()
            return round(end - self.started_at, 2)
        return 0.0

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'status': self.status.value,
            'renderer': self.renderer,
            'format': self.format,
            'error': self.error,
            'elapsed': self.elapsed,
            'progress_pct': self.progress_pct,
            'progress_msg': self.progress_msg,
            'output_ready': self.status == JobStatus.COMPLETED and self.output_path is not None,
        }


class AsyncRenderManager:
    """Manage background rendering jobs."""

    JOB_TTL = 3600  # 1 hour
    MAX_CONCURRENT = 3

    def __init__(self):
        self._jobs: Dict[str, RenderJob] = {}
        self._lock = threading.Lock()
        self._semaphore = threading.Semaphore(self.MAX_CONCURRENT)

    def submit(
        self,
        workflow_text: str,
        title: str = 'Workflow',
        renderer: str = 'mermaid',
        format: str = 'png',
        extraction: str = 'auto',
        theme: str = 'default',
        model_path: Optional[str] = None,
        ollama_base_url: str = 'http://localhost:11434',
        ollama_model: Optional[str] = None,
        graphviz_engine: str = 'dot',
        d2_layout: str = 'elk',
        kroki_url: str = 'http://localhost:8000',
    ) -> str:
        """Submit a background rendering job. Returns job ID."""
        self._cleanup_expired()

        job_id = str(uuid.uuid4())[:12]
        job = RenderJob(id=job_id, renderer=renderer, format=format)

        with self._lock:
            self._jobs[job_id] = job

        # Run in background thread
        thread = threading.Thread(
            target=self._execute,
            args=(job, workflow_text, title, extraction, theme,
                  model_path, ollama_base_url, ollama_model, graphviz_engine, d2_layout, kroki_url),
            daemon=True,
        )
        thread.start()

        return job_id

    def get_status(self, job_id: str) -> Optional[Dict]:
        """Get job status."""
        job = self._jobs.get(job_id)
        if not job:
            return None
        return job.to_dict()

    def get_output_path(self, job_id: str) -> Optional[str]:
        """Get output file path for completed job."""
        job = self._jobs.get(job_id)
        if job and job.status == JobStatus.COMPLETED and job.output_path:
            if Path(job.output_path).exists():
                return job.output_path
        return None

    def _execute(
        self,
        job: RenderJob,
        workflow_text: str,
        title: str,
        extraction: str,
        theme: str,
        model_path: Optional[str],
        ollama_base_url: str,
        ollama_model: Optional[str],
        graphviz_engine: str,
        d2_layout: str,
        kroki_url: str,
    ):
        """Execute rendering job in background thread."""
        self._semaphore.acquire()
        try:
            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            job.progress_pct = 10
            job.progress_msg = 'Initializing pipeline...'

            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from src.pipeline import FlowchartPipeline, PipelineConfig

            config = PipelineConfig(
                extraction=extraction,
                renderer=job.renderer,
                model_path=model_path,
                ollama_base_url=ollama_base_url,
                ollama_model=ollama_model,
                theme=theme,
                graphviz_engine=graphviz_engine,
                d2_layout=d2_layout,
                kroki_url=kroki_url,
            )
            pipeline = FlowchartPipeline(config)

            # Extract
            job.progress_pct = 30
            job.progress_msg = f'Extracting steps via {extraction}...'
            steps = pipeline.extract_steps(workflow_text)

            if not steps:
                job.status = JobStatus.FAILED
                job.error = 'No workflow steps detected'
                return

            # Build
            job.progress_pct = 55
            job.progress_msg = f'Building flowchart from {len(steps)} steps...'
            flowchart = pipeline.build_flowchart(steps, title=title)

            # Render
            job.progress_pct = 75
            job.progress_msg = f'Rendering via {job.renderer}...'

            suffix = f'.{job.format}'
            output_path = str(TMP_ROOT / f"flowchart_{job.id}_{int(time.time())}{suffix}")

            success = pipeline.render(flowchart, output_path, format=job.format)

            if success and Path(output_path).exists() and Path(output_path).stat().st_size > 0:
                job.status = JobStatus.COMPLETED
                job.output_path = output_path
                job.progress_pct = 100
                job.progress_msg = 'Complete!'
            else:
                # Try HTML fallback
                job.progress_msg = f'{job.renderer} failed, trying HTML fallback...'
                html_path = output_path.replace(suffix, '.html')
                success = pipeline._render_html(flowchart, html_path)
                if success:
                    job.status = JobStatus.COMPLETED
                    job.output_path = html_path
                    job.format = 'html'
                    job.progress_pct = 100
                    job.progress_msg = 'Complete (HTML fallback)'
                else:
                    job.status = JobStatus.FAILED
                    job.error = f'{job.renderer} rendering failed'

        except Exception as e:
            logger.error(f"Async render job {job.id} failed: {e}", exc_info=True)
            job.status = JobStatus.FAILED
            job.error = str(e)

        finally:
            job.completed_at = time.time()
            self._semaphore.release()

    def _cleanup_expired(self):
        """Remove expired jobs."""
        now = time.time()
        with self._lock:
            expired = [
                jid for jid, job in self._jobs.items()
                if now - job.created_at > self.JOB_TTL
            ]
            for jid in expired:
                job = self._jobs.pop(jid, None)
                if job and job.output_path:
                    try:
                        Path(job.output_path).unlink(missing_ok=True)
                    except Exception:
                        pass


# Singleton instance
render_manager = AsyncRenderManager()
