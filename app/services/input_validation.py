def validate_journal(text: str, max_characters: int) -> str | None:
    if not text.strip():
        return "Tuliskan jurnal sebelum menilai."
    if len(text) > max_characters:
        return f"Jurnal melebihi batas {max_characters:,} karakter."
    return None
