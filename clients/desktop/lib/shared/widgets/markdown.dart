import 'package:flutter/material.dart' show SelectableText;
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

import '../../core/theme/icons.dart';
import '../../core/theme/magnus_theme.dart';

/// Markdown de andar por casa, el que de verdad escriben los modelos.
///
/// No se usa un paquete: solo hacen falta títulos, listas, negritas, cursivas,
/// código en línea y bloques de código. Con eso una respuesta se lee bien, y a
/// cambio la app no arrastra una dependencia más ni un tema aparte que se
/// desalinee del resto.
///
/// El texto sigue siendo seleccionable y copiable, que es lo que la gente hace
/// con la respuesta de un modelo.
class MarkdownText extends StatelessWidget {
  const MarkdownText(this.text, {super.key, this.color, this.selectable = true});

  final String text;
  final Color? color;
  final bool selectable;

  @override
  Widget build(BuildContext context) {
    final bloques = _parse(text);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        for (var i = 0; i < bloques.length; i++)
          Padding(
            padding: EdgeInsets.only(bottom: i == bloques.length - 1 ? 0 : 8),
            child: bloques[i].build(context, color: color, selectable: selectable),
          ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Bloques
// ---------------------------------------------------------------------------

abstract class _Block {
  Widget build(BuildContext context, {Color? color, bool selectable = true});
}

class _Paragraph implements _Block {
  const _Paragraph(this.text, {this.level = 0, this.bullet, this.indent = 0});

  final String text;
  final int level; // 0 = párrafo; 1..3 = título
  final String? bullet; // "•" o "1." si es lista
  final double indent;

  @override
  Widget build(BuildContext context, {Color? color, bool selectable = true}) {
    final t = MagnusTheme.of(context);
    final base = switch (level) {
      1 => t.h1.copyWith(fontSize: 19),
      2 => t.h2.copyWith(fontSize: 16),
      3 => t.h2.copyWith(fontSize: 14.5),
      _ => t.body,
    };
    final estilo = base.copyWith(color: color ?? base.color);
    final span = TextSpan(children: _inline(text, estilo, t));
    final cuerpo = selectable
        ? SelectableText.rich(span, style: estilo)
        : Text.rich(span, style: estilo);
    if (bullet == null) return Padding(padding: EdgeInsets.only(left: indent), child: cuerpo);
    return Padding(
      padding: EdgeInsets.only(left: indent),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 22,
            child: Text(bullet!, style: estilo.copyWith(color: t.accent)),
          ),
          Expanded(child: cuerpo),
        ],
      ),
    );
  }
}

class _CodeBlock implements _Block {
  const _CodeBlock(this.code, this.language);

  final String code;
  final String language;

  @override
  Widget build(BuildContext context, {Color? color, bool selectable = true}) =>
      _CodeCard(code: code, language: language);
}

/// Bloque de código con su lenguaje y un botón para copiarlo.
class _CodeCard extends StatefulWidget {
  const _CodeCard({required this.code, required this.language});

  final String code;
  final String language;

  @override
  State<_CodeCard> createState() => _CodeCardState();
}

class _CodeCardState extends State<_CodeCard> {
  bool _copiado = false;

  Future<void> _copiar() async {
    await Clipboard.setData(ClipboardData(text: widget.code));
    if (!mounted) return;
    setState(() => _copiado = true);
    await Future<void>.delayed(const Duration(seconds: 2));
    if (mounted) setState(() => _copiado = false);
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: t.isDark ? const Color(0x33000000) : t.surfaceAlt,
        borderRadius: BorderRadius.circular(t.radius),
        border: Border.all(color: t.stroke),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 8, 4),
            child: Row(
              children: [
                Text(widget.language.isEmpty ? 'código' : widget.language,
                    style: t.small.copyWith(color: t.textFaint, fontSize: 11)),
                const Spacer(),
                GestureDetector(
                  onTap: _copiar,
                  child: MouseRegion(
                    cursor: SystemMouseCursors.click,
                    child: Row(
                      children: [
                        Icon(_copiado ? context.icons.check : context.icons.document,
                            size: 13, color: _copiado ? t.ok : t.textMuted),
                        const SizedBox(width: 5),
                        Text(_copiado ? 'copiado' : 'copiar',
                            style: t.small.copyWith(
                                fontSize: 11, color: _copiado ? t.ok : t.textMuted)),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: SelectableText(widget.code, style: t.mono),
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Análisis
// ---------------------------------------------------------------------------

final _bullet = RegExp(r'^(\s*)[-*+]\s+(.*)$');
final _numbered = RegExp(r'^(\s*)(\d+)[.)]\s+(.*)$');
final _heading = RegExp(r'^(#{1,3})\s+(.*)$');

List<_Block> _parse(String texto) {
  final bloques = <_Block>[];
  final lineas = texto.split('\n');
  final parrafo = <String>[];

  void cerrarParrafo() {
    if (parrafo.isEmpty) return;
    bloques.add(_Paragraph(parrafo.join('\n').trim()));
    parrafo.clear();
  }

  for (var i = 0; i < lineas.length; i++) {
    final linea = lineas[i];

    // Bloque de código: se traga todo hasta el cierre (o hasta el final, que es
    // lo que pasa mientras la respuesta se está escribiendo).
    if (linea.trimLeft().startsWith('```')) {
      cerrarParrafo();
      final lenguaje = linea.trim().substring(3).trim();
      final codigo = <String>[];
      i++;
      while (i < lineas.length && !lineas[i].trimLeft().startsWith('```')) {
        codigo.add(lineas[i]);
        i++;
      }
      bloques.add(_CodeBlock(codigo.join('\n'), lenguaje));
      continue;
    }

    if (linea.trim().isEmpty) {
      cerrarParrafo();
      continue;
    }

    final titulo = _heading.firstMatch(linea);
    if (titulo != null) {
      cerrarParrafo();
      bloques.add(_Paragraph(titulo.group(2)!, level: titulo.group(1)!.length));
      continue;
    }

    final vineta = _bullet.firstMatch(linea);
    if (vineta != null) {
      cerrarParrafo();
      bloques.add(_Paragraph(vineta.group(2)!,
          bullet: '•', indent: vineta.group(1)!.length / 2 * 14));
      continue;
    }

    final numerada = _numbered.firstMatch(linea);
    if (numerada != null) {
      cerrarParrafo();
      bloques.add(_Paragraph(numerada.group(3)!,
          bullet: '${numerada.group(2)}.', indent: numerada.group(1)!.length / 2 * 14));
      continue;
    }

    parrafo.add(linea);
  }
  cerrarParrafo();
  return bloques.isEmpty ? [const _Paragraph('')] : bloques;
}

/// Negritas, cursivas y código en línea dentro de un párrafo.
final _inlinePattern = RegExp(r'(\*\*|__)(.+?)\1|(\*|_)(.+?)\3|`([^`]+)`');

List<InlineSpan> _inline(String texto, TextStyle base, MagnusTheme t) {
  final spans = <InlineSpan>[];
  var pos = 0;
  for (final m in _inlinePattern.allMatches(texto)) {
    if (m.start > pos) spans.add(TextSpan(text: texto.substring(pos, m.start)));
    if (m.group(2) != null) {
      spans.add(TextSpan(text: m.group(2), style: const TextStyle(fontWeight: FontWeight.w700)));
    } else if (m.group(4) != null) {
      spans.add(TextSpan(text: m.group(4), style: const TextStyle(fontStyle: FontStyle.italic)));
    } else if (m.group(5) != null) {
      spans.add(TextSpan(
        text: m.group(5),
        style: t.mono.copyWith(
          fontSize: base.fontSize == null ? null : base.fontSize! - 0.5,
          color: t.accent,
          backgroundColor: t.accentSoft,
        ),
      ));
    }
    pos = m.end;
  }
  if (pos < texto.length) spans.add(TextSpan(text: texto.substring(pos)));
  return spans;
}
