import 'package:flutter/widgets.dart';

import '../../core/theme/magnus_theme.dart';

/// Fondo de la ventana: degradado sutil con tinte de acento. Sobre Acrylic
/// (Windows) deja translucidez; en Material/Apple da profundidad al fondo.
Gradient shellBackdrop(MagnusTheme t) {
  if (t.isDark) {
    return LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [
        Color.alphaBlend(t.accent.withValues(alpha: 0.10), t.bg.withValues(alpha: 0.92)),
        t.bg.withValues(alpha: 0.94),
        Color.alphaBlend(const Color(0xFF000000).withValues(alpha: 0.10), t.bg.withValues(alpha: 0.95)),
      ],
      stops: const [0.0, 0.5, 1.0],
    );
  }
  return LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      Color.alphaBlend(t.accent.withValues(alpha: 0.06), t.bg.withValues(alpha: 0.96)),
      t.bg.withValues(alpha: 0.98),
    ],
  );
}

/// Marca de Magnus: marca con monograma "M" en degradado + wordmark.
/// Se contrae a solo el monograma cuando [extended] es falso.
class ShellBrand extends StatelessWidget {
  const ShellBrand({super.key, required this.theme, this.extended = true});
  final MagnusTheme theme;
  final bool extended;

  @override
  Widget build(BuildContext context) {
    final t = theme;
    final mark = Container(
      width: 34,
      height: 34,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [t.accent, Color.alphaBlend(t.info.withValues(alpha: 0.6), t.accent)],
        ),
        borderRadius: BorderRadius.circular(9),
        boxShadow: [BoxShadow(color: t.accent.withValues(alpha: 0.45), blurRadius: 12, offset: const Offset(0, 4))],
      ),
      alignment: Alignment.center,
      child: const Text('M',
          style: TextStyle(
              color: Color(0xFFFFFFFF),
              fontSize: 18,
              fontWeight: FontWeight.w800,
              height: 1)),
    );

    return Padding(
      padding: EdgeInsets.fromLTRB(extended ? 16 : 0, 18, 16, 14),
      child: Row(
        mainAxisAlignment:
            extended ? MainAxisAlignment.start : MainAxisAlignment.center,
        children: [
          mark,
          if (extended) ...[
            const SizedBox(width: 11),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('Magnus',
                    style: TextStyle(
                        color: t.text,
                        fontSize: 17,
                        fontWeight: FontWeight.w700,
                        letterSpacing: -0.2,
                        height: 1.1)),
                Text('agent OS',
                    style: TextStyle(
                        color: t.textFaint,
                        fontSize: 10.5,
                        fontWeight: FontWeight.w500,
                        letterSpacing: 1.2)),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
