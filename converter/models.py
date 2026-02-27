from django.db import models
import json

class LearningPattern(models.Model):
    """Modelo para armazenar padrões aprendidos para detecção de colunas"""
    pattern_type = models.CharField(max_length=50)  # 'endereco', 'id', 'hora', etc.
    pattern_value = models.CharField(max_length=255)  # agora é CharField para MySQL
    confidence = models.FloatField(default=1.0)  # confiança do padrão
    usage_count = models.IntegerField(default=1)  # quantas vezes foi usado
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['pattern_type', 'pattern_value']  # funciona no MySQL agora

class ProcessingHistory(models.Model):
    """Histórico de processamentos para aprendizado"""
    original_data = models.TextField()  # dados originais
    processed_data = models.TextField()  # dados processados (JSON)
    user_corrections = models.TextField(blank=True)  # correções do usuário (JSON)
    created_at = models.DateTimeField(auto_now_add=True)

