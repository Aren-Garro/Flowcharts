"""Hardware and software capability detection for adaptive pipeline routing.

Phase 5: Probes system for GPU availability, RAM capacity, installed binaries,
and Docker containers to automatically select the best extraction method and
rendering engine for the current environment.
"""

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SystemCapabilities:
    """Snapshot of detected system capabilities."""

    # Hardware
    total_ram_gb: float = 0.0
    available_ram_gb: float = 0.0
    cpu_count: int = 1
    platform: str = ""
    arch: str = ""

    # GPU
    has_cuda: bool = False
    has_metal: bool = False
    cuda_device_name: Optional[str] = None
    cuda_vram_gb: float = 0.0
    gpu_backend: Optional[str] = None  # 'cuda', 'metal', 'cpu'

    # Python packages
    has_llama_cpp: bool = False
    has_instructor: bool = False
    has_graphviz_python: bool = False
    has_spacy: bool = False
    has_flask_socketio: bool = False

    # Binaries
    has_graphviz_binary: bool = False
    has_d2_binary: bool = False
    has_mmdc_binary: bool = False
    has_node: bool = False
    has_docker: bool = False

    # Services
    kroki_available: bool = False
    kroki_url: str = "http://localhost:8000"
    ollama_available: bool = False
    ollama_reachable: bool = False
    ollama_base_url: str = "http://localhost:11434"
    ollama_models_count: int = 0
    ollama_recommended_model: Optional[str] = None

    # Derived recommendations
    recommended_extraction: str = "heuristic"
    recommended_renderer: str = "mermaid"
    available_extractors: List[str] = field(default_factory=lambda: ["heuristic"])
    available_renderers: List[str] = field(default_factory=lambda: ["mermaid", "html"])
    warnings: List[str] = field(default_factory=list)


class CapabilityDetector:
    """Detect system capabilities for adaptive pipeline routing.

    Probes hardware, installed packages, system binaries, and running
    services to determine optimal extraction and rendering strategies.
    """

    def __init__(self, kroki_url: str = "http://localhost:8000", ollama_base_url: str = "http://localhost:11434"):
        self.kroki_url = kroki_url
        self.ollama_base_url = ollama_base_url
        self._cache: Optional[SystemCapabilities] = None

    def detect(self, force_refresh: bool = False) -> SystemCapabilities:
        """Run full system capability detection.

        Results are cached after first call unless force_refresh=True.
        """
        if self._cache is not None and not force_refresh:
            return self._cache

        caps = SystemCapabilities()
        caps.platform = platform.system()
        caps.arch = platform.machine()
        caps.cpu_count = os.cpu_count() or 1

        self._detect_ram(caps)
        self._detect_gpu(caps)
        self._detect_python_packages(caps)
        self._detect_binaries(caps)
        self._detect_services(caps)
        self._compute_recommendations(caps)

        self._cache = caps
        return caps

    # ── Hardware ──

    def _detect_ram(self, caps: SystemCapabilities):
        """Detect total and available RAM."""
        try:
            import psutil
            mem = psutil.virtual_memory()
            caps.total_ram_gb = round(mem.total / (1024 ** 3), 1)
            caps.available_ram_gb = round(mem.available / (1024 ** 3), 1)
        except ImportError:
            # Fallback: read /proc/meminfo on Linux
            try:
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if line.startswith('MemTotal:'):
                            caps.total_ram_gb = round(int(line.split()[1]) / (1024 ** 2), 1)
                        elif line.startswith('MemAvailable:'):
                            caps.available_ram_gb = round(int(line.split()[1]) / (1024 ** 2), 1)
            except Exception:
                caps.warnings.append("Could not detect RAM. Install psutil for accurate detection.")

    def _detect_gpu(self, caps: SystemCapabilities):
        """Detect GPU availability for LLM acceleration."""
        # CUDA detection
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(',')
                caps.has_cuda = True
                caps.cuda_device_name = parts[0].strip()
                if len(parts) > 1:
                    caps.cuda_vram_gb = round(float(parts[1].strip()) / 1024, 1)
                caps.gpu_backend = 'cuda'
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Metal detection (macOS)
        if caps.platform == 'Darwin' and not caps.has_cuda:
            try:
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True, text=True, timeout=5
                )
                if 'Metal' in result.stdout:
                    caps.has_metal = True
                    caps.gpu_backend = 'metal'
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        if not caps.gpu_backend:
            caps.gpu_backend = 'cpu'

    # ── Python Packages ──

    def _detect_python_packages(self, caps: SystemCapabilities):
        """Check for installed Python packages."""
        checks = {
            'has_llama_cpp': 'llama_cpp',
            'has_instructor': 'instructor',
            'has_graphviz_python': 'graphviz',
            'has_spacy': 'spacy',
            'has_flask_socketio': 'flask_socketio',
        }
        for attr, module in checks.items():
            try:
                __import__(module)
                setattr(caps, attr, True)
            except Exception:
                setattr(caps, attr, False)

    # ── System Binaries ──

    def _detect_binaries(self, caps: SystemCapabilities):
        """Check for installed system binaries."""
        caps.has_graphviz_binary = shutil.which('dot') is not None
        caps.has_d2_binary = shutil.which('d2') is not None
        caps.has_mmdc_binary = shutil.which('mmdc') is not None
        caps.has_node = shutil.which('node') is not None
        caps.has_docker = shutil.which('docker') is not None

    # ── Services ──

    def _detect_services(self, caps: SystemCapabilities):
        """Check for running services (Kroki, etc.)."""
        caps.kroki_url = self.kroki_url
        caps.ollama_base_url = self.ollama_base_url
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.kroki_url}/health", method='GET')
            with urllib.request.urlopen(req, timeout=3) as resp:
                caps.kroki_available = resp.status == 200
        except Exception:
            caps.kroki_available = False

        ollama_info = self.detect_ollama(caps.ollama_base_url)
        caps.ollama_available = bool(ollama_info.get("available"))
        caps.ollama_reachable = bool(ollama_info.get("reachable"))
        caps.ollama_models_count = len(ollama_info.get("models") or [])
        if caps.ollama_models_count:
            caps.ollama_recommended_model = ollama_info["models"][0].get("name")
        for warn in ollama_info.get("warnings") or []:
            caps.warnings.append(warn)

    # ── Recommendation Engine ──

    def _compute_recommendations(self, caps: SystemCapabilities):
        """Compute best extraction method and renderer based on capabilities."""
        # Available extractors
        caps.available_extractors = ['heuristic']  # Always available
        if caps.ollama_available:
            caps.available_extractors.append('ollama')

        if caps.has_llama_cpp and caps.has_instructor:
            # Need at least 5GB available RAM for Q4 model
            if caps.available_ram_gb >= 5.0 or caps.has_cuda or caps.has_metal:
                caps.available_extractors.append('local-llm')
            else:
                caps.warnings.append(
                    f"local-llm available but only {caps.available_ram_gb}GB RAM free. "
                    "Recommend 5GB+ for Q4_K_M quantization."
                )

        # Available renderers
        caps.available_renderers = ['html']  # Pure Python, always available

        if caps.has_mmdc_binary or caps.has_node:
            caps.available_renderers.append('mermaid')
        else:
            caps.available_renderers.append('mermaid')  # HTML fallback
            caps.warnings.append(
                "mermaid-cli not found. Mermaid will use HTML output only. "
                "Install: npm install -g @mermaid-js/mermaid-cli"
            )

        if caps.has_graphviz_python and caps.has_graphviz_binary:
            caps.available_renderers.append('graphviz')

        if caps.has_d2_binary:
            caps.available_renderers.append('d2')

        if caps.kroki_available:
            caps.available_renderers.append('kroki')

        # Best extraction
        if 'ollama' in caps.available_extractors:
            caps.recommended_extraction = 'ollama'
        elif 'local-llm' in caps.available_extractors:
            caps.recommended_extraction = 'local-llm'
        else:
            caps.recommended_extraction = 'heuristic'

        # Best renderer (prefer native over browser-based)
        if 'graphviz' in caps.available_renderers:
            caps.recommended_renderer = 'graphviz'
        elif 'd2' in caps.available_renderers:
            caps.recommended_renderer = 'd2'
        elif 'mermaid' in caps.available_renderers and caps.has_mmdc_binary:
            caps.recommended_renderer = 'mermaid'
        elif 'kroki' in caps.available_renderers:
            caps.recommended_renderer = 'kroki'
        else:
            caps.recommended_renderer = 'html'

    def detect_ollama(self, base_url: Optional[str] = None) -> Dict:
        """Probe Ollama service and list local models."""
        try:
            from src.parser.ollama_extractor import discover_ollama_models
        except Exception:
            return {
                "available": False,
                "reachable": False,
                "base_url": base_url or self.ollama_base_url,
                "models": [],
                "warnings": ["Ollama probe unavailable: parser module import failed."],
                "error": "import_error",
            }

        info = discover_ollama_models(base_url=base_url or self.ollama_base_url)
        if not info.get("reachable"):
            info.setdefault("warnings", []).append(
                f"Ollama not reachable at {info.get('base_url')}. Start Ollama to enable ollama extraction."
            )
        return info

    def get_summary(self) -> Dict:
        """Return a JSON-friendly summary of capabilities."""
        caps = self.detect()
        return {
            'hardware': {
                'platform': caps.platform,
                'arch': caps.arch,
                'cpu_count': caps.cpu_count,
                'total_ram_gb': caps.total_ram_gb,
                'available_ram_gb': caps.available_ram_gb,
                'gpu_backend': caps.gpu_backend,
                'cuda_device': caps.cuda_device_name,
                'cuda_vram_gb': caps.cuda_vram_gb,
            },
            'extractors': {
                'available': caps.available_extractors,
                'recommended': caps.recommended_extraction,
                'details': {
                    'heuristic': {'ready': True, 'note': 'spaCy + EntityRuler'},
                    'ollama': {
                        'ready': 'ollama' in caps.available_extractors,
                        'reachable': caps.ollama_reachable,
                        'base_url': caps.ollama_base_url,
                        'models_count': caps.ollama_models_count,
                        'recommended_model': caps.ollama_recommended_model,
                    },
                    'local-llm': {
                        'ready': 'local-llm' in caps.available_extractors,
                        'has_llama_cpp': caps.has_llama_cpp,
                        'has_instructor': caps.has_instructor,
                        'gpu': caps.gpu_backend,
                    },
                },
            },
            'renderers': {
                'available': caps.available_renderers,
                'recommended': caps.recommended_renderer,
                'details': {
                    'mermaid': {'ready': True, 'image_export': caps.has_mmdc_binary},
                    'graphviz': {'ready': 'graphviz' in caps.available_renderers, 'binary': caps.has_graphviz_binary},
                    'd2': {'ready': 'd2' in caps.available_renderers, 'binary': caps.has_d2_binary},
                    'kroki': {'ready': caps.kroki_available, 'url': caps.kroki_url},
                    'html': {'ready': True, 'note': 'Pure Python, always available'},
                },
            },
            'warnings': caps.warnings,
        }

    def validate_config(self, config) -> List[str]:
        """Validate a PipelineConfig against detected capabilities.

        Returns list of warning messages. Empty list means config is valid.
        """
        caps = self.detect()
        issues = []

        if config.extraction == 'ollama' and 'ollama' not in caps.available_extractors:
            issues.append(
                f"Ollama not ready at {caps.ollama_base_url}. "
                "Start Ollama and ensure at least one model is pulled."
            )

        if config.extraction == 'local-llm' and 'local-llm' not in caps.available_extractors:
            if not caps.has_llama_cpp:
                issues.append("local-llm requires llama-cpp-python. Install: pip install llama-cpp-python")
            if not caps.has_instructor:
                issues.append("local-llm requires instructor. Install: pip install instructor")
            if caps.available_ram_gb < 5.0 and not (caps.has_cuda or caps.has_metal):
                issues.append(
                    f"Only {caps.available_ram_gb}GB RAM available. "
                    "local-llm needs ~5GB for Q4 quantization."
                )

        if config.renderer == 'graphviz' and 'graphviz' not in caps.available_renderers:
            issues.append("Graphviz not available. Install: pip install graphviz && apt install graphviz")

        if config.renderer == 'd2' and 'd2' not in caps.available_renderers:
            issues.append("D2 binary not found. Install from https://d2lang.com")

        if config.renderer == 'kroki' and not caps.kroki_available:
            issues.append(f"Kroki not reachable at {caps.kroki_url}. Start: docker run -d -p 8000:8000 yuzutech/kroki")

        return issues
