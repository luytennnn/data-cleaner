# Exceções do motor — mensagens claras para a UI apresentar ao utilizador
class DataCleanerError(Exception):
    """Erro base do motor; a app apresenta str(e) diretamente."""


class EmptyDataError(DataCleanerError):
    """Ficheiro sem dados (vazio ou só cabeçalho)."""


class UnsupportedFormatError(DataCleanerError):
    """Extensão de ficheiro não suportada."""


class ColumnNotFoundError(DataCleanerError):
    """Coluna-chave escolhida não existe no DataFrame."""
