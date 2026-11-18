// Búsqueda tolerante a tildes, orden de palabras y separadores en códigos industriales.
// No se corrigen automáticamente dígitos ni letras de modelos (evita falsos positivos).
export const normalized = (value: string | null | undefined) =>
  (value ?? '').toLocaleLowerCase('es').normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, ' ').trim();

const compact = (value: string) => normalized(value).replace(/\s+/g, '');

export function rankMatch(query: string, fields: { value: string | null | undefined; weight: number }[]): number {
  const words = normalized(query).split(/\s+/).filter(Boolean);
  if (!words.length) return 0;
  const data = fields.map(f => ({ text: normalized(f.value), code: compact(f.value ?? ''), weight: f.weight }));
  let score = 0;
  for (const word of words) {
    const compactWord = compact(word);
    const matches = data
      .filter(d => d.text.includes(word) || (compactWord.length >= 3 && d.code.includes(compactWord)))
      .map(d => d.weight + (d.text === word || d.code === compactWord ? 30 : d.text.startsWith(word) ? 15 : 0));
    if (!matches.length) return -1; // AND: deben encontrarse todos los términos
    score += Math.max(...matches);
  }
  return score;
}
