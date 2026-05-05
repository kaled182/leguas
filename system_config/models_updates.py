"""Modelos do módulo de Atualização: changelog, sugestões e versão."""
import re

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


def today_version_base(d=None):
    """Devolve o prefixo de versão do dia: 'beta-DD-MM'."""
    d = d or timezone.now().date()
    return f"beta-{d.day:02d}-{d.month:02d}"


def suggest_next_version():
    """Sugere a próxima versão para o dia de hoje.

    Regra: se já existe entrada para hoje com versão `beta-DD-MM.N`,
    sugere `beta-DD-MM.(N+1)`. Caso contrário, sugere `beta-DD-MM.1`.
    Sub-versões (ex: .1.1) são geridas manualmente pelo admin.
    """
    today = timezone.now().date()
    base = today_version_base(today)
    entry = ChangelogEntry.objects.filter(date=today).first()
    if not entry or not entry.version:
        return f"{base}.1"
    m = re.match(rf"{re.escape(base)}\.(\d+)", entry.version)
    if m:
        return f"{base}.{int(m.group(1)) + 1}"
    return f"{base}.1"


class ChangelogEntry(models.Model):
    """Uma entrada de changelog por dia. Aglomera todas as alterações.

    A `version` é a versão mais recente do dia (ex: `beta-05-05.3`).
    Sub-versões (`.1.1`) são guardadas em `version_history` (lista JSON).
    """

    date = models.DateField(
        "Data", unique=True, default=timezone.now,
        help_text="Apenas uma entrada por dia. Aglomera todas as alterações.",
    )
    version = models.CharField(
        "Versão actual", max_length=40,
        help_text="Ex: beta-05-05.3. Auto-gerada por defeito.",
    )
    version_history = models.JSONField(
        "Histórico de versões", default=list, blank=True,
        help_text="Lista de versões emitidas neste dia.",
    )
    content = models.TextField(
        "Conteúdo do changelog",
        help_text="Markdown ou texto livre. Lista as alterações deste dia.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="changelog_entries_created",
    )
    # Publicação automática no GitHub
    published_at = models.DateTimeField(
        "Publicado no GitHub em", null=True, blank=True,
    )
    published_commit_sha = models.CharField(
        "SHA do commit publicado", max_length=40, blank=True,
    )
    publish_status = models.CharField(
        "Estado de publicação", max_length=20,
        default="PENDING",
        choices=[
            ("PENDING", "Por publicar"),
            ("PUBLISHED", "Publicado"),
            ("FAILED", "Falhou"),
        ],
    )
    publish_error = models.TextField("Último erro de publicação", blank=True)

    class Meta:
        verbose_name = "Entrada de Changelog"
        verbose_name_plural = "Changelog"
        ordering = ["-date"]

    def __str__(self):
        return f"{self.version} — {self.date.strftime('%d/%m/%Y')}"

    def save(self, *args, **kwargs):
        # Auto-popular history com a versão actual
        if self.version and self.version not in (self.version_history or []):
            history = list(self.version_history or [])
            history.append(self.version)
            self.version_history = history
        super().save(*args, **kwargs)


class Suggestion(models.Model):
    """Sugestão de melhoria submetida por um utilizador."""

    STATUS_CHOICES = [
        ("NEW", "Nova"),
        ("REVIEWING", "Em análise"),
        ("PLANNED", "Planeada"),
        ("DONE", "Implementada"),
        ("REJECTED", "Rejeitada"),
    ]

    CATEGORY_CHOICES = [
        ("UI", "Interface / Usabilidade"),
        ("FEATURE", "Nova funcionalidade"),
        ("PERFORMANCE", "Performance"),
        ("BUG", "Bug / Defeito"),
        ("OTHER", "Outro"),
    ]

    title = models.CharField("Título", max_length=200)
    description = models.TextField("Descrição")
    category = models.CharField(
        "Categoria", max_length=20, choices=CATEGORY_CHOICES, default="OTHER",
    )
    submitter = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="suggestions_submitted",
    )
    submitter_name = models.CharField(
        "Nome do autor", max_length=120, blank=True,
        help_text="Preenchido quando o autor não está autenticado.",
    )
    status = models.CharField(
        "Estado", max_length=20, choices=STATUS_CHOICES, default="NEW",
        db_index=True,
    )
    admin_response = models.TextField("Resposta do admin", blank=True)
    related_changelog = models.ForeignKey(
        ChangelogEntry, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="suggestions_addressed",
        help_text="Versão na qual a sugestão foi implementada.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Sugestão"
        verbose_name_plural = "Sugestões"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class SystemVersionState(models.Model):
    """Singleton — estado da versão deployada e info do repositório GitHub."""

    current_version = models.CharField(
        "Versão deployada", max_length=40, blank=True,
    )
    deployed_commit_hash = models.CharField(
        "Commit deployado (SHA)", max_length=40, blank=True,
        db_index=True,
    )
    deployed_at = models.DateTimeField("Deployado em", null=True, blank=True)
    github_repo_url = models.CharField(
        "URL do repositório GitHub", max_length=300, blank=True,
        default="https://github.com/kaled182/leguas",
        help_text="Ex: https://github.com/kaled182/leguas",
    )
    github_branch = models.CharField(
        "Branch", max_length=80, default="main",
    )
    github_token = models.CharField(
        "GitHub Token (opcional, para repos privados)",
        max_length=200, blank=True,
    )
    last_check_at = models.DateTimeField(
        "Última verificação", null=True, blank=True,
    )
    last_check_result = models.JSONField(
        "Último resultado", default=dict, blank=True,
    )

    class Meta:
        verbose_name = "Estado da Versão"
        verbose_name_plural = "Estado da Versão"

    def __str__(self):
        return self.current_version or "(sem versão)"

    @classmethod
    def get(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        # Garante URL default na primeira utilização
        if created or not obj.github_repo_url:
            obj.github_repo_url = "https://github.com/kaled182/leguas"
            obj.github_branch = obj.github_branch or "main"
            obj.save(update_fields=["github_repo_url", "github_branch"])
        return obj
