import 'package:flutter/widgets.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../core/theme/brand.dart';
import '../../core/theme/magnus_theme.dart';

/// Fondo de la ventana, el mismo gesto que la web: tinta nocturna con dos
/// luces quietas — violeta arriba a la izquierda, celeste abajo a la derecha.
///
/// Es estático a propósito: el fondo está siempre en pantalla y animarlo gasta
/// GPU que en Magnus es para los modelos. La aurora animada queda para las
/// cabeceras (`AuroraBackdrop`).
class ShellBackdrop extends StatelessWidget {
  const ShellBackdrop({super.key, required this.theme, required this.child, this.opaque = true});
  final MagnusTheme theme;
  final Widget child;

  /// En Windows el fondo deja pasar un poco del Acrylic de la ventana.
  final bool opaque;

  @override
  Widget build(BuildContext context) {
    final t = theme;
    final glow = t.isDark ? 0.20 : 0.10;
    return DecoratedBox(
      decoration: BoxDecoration(color: opaque ? t.bg : t.bg.withValues(alpha: 0.90)),
      child: CustomPaint(
        painter: _GlowPainter(
          first: t.accent.withValues(alpha: glow),
          second: Brand.sky.withValues(alpha: glow * 0.55),
        ),
        child: child,
      ),
    );
  }
}

class _GlowPainter extends CustomPainter {
  const _GlowPainter({required this.first, required this.second});
  final Color first;
  final Color second;

  @override
  void paint(Canvas canvas, Size size) {
    void glow(Offset center, double radius, Color color) {
      final rect = Rect.fromCircle(center: center, radius: radius);
      canvas.drawRect(
        Offset.zero & size,
        Paint()
          ..shader = RadialGradient(colors: [color, color.withValues(alpha: 0)])
              .createShader(rect),
      );
    }

    final r = size.longestSide;
    glow(Offset(size.width * 0.12, -size.height * 0.10), r * 0.62, first);
    glow(Offset(size.width * 1.02, size.height * 1.05), r * 0.55, second);
  }

  @override
  bool shouldRepaint(_GlowPainter old) => old.first != first || old.second != second;
}

/// Monograma de Magnus: una M hecha de barras de nivel (lectura de VRAM y
/// tokens). La barra central en ámbar es el ahorro. Fiel a `brand/magnus-mark.svg`.
class MagnusMark extends StatelessWidget {
  const MagnusMark({super.key, this.size = 28, this.color});
  final double size;

  /// Color de las barras exteriores; por defecto el violeta de marca.
  final Color? color;

  @override
  Widget build(BuildContext context) => SizedBox.square(
        dimension: size,
        child: CustomPaint(painter: _MarkPainter(color ?? Brand.violet)),
      );
}

class _MarkPainter extends CustomPainter {
  const _MarkPainter(this.bar);
  final Color bar;

  // (x, y, alto) en la retícula de 64 del SVG; ancho 8 y radio 2.
  static const _bars = [(4.0, 8.0, 48.0), (16.0, 22.0, 34.0), (28.0, 36.0, 20.0),
    (40.0, 22.0, 34.0), (52.0, 8.0, 48.0)];

  @override
  void paint(Canvas canvas, Size size) {
    final s = size.width / 64;
    for (var i = 0; i < _bars.length; i++) {
      final (x, y, h) = _bars[i];
      final paint = Paint()..color = i == 2 ? Brand.amber : bar;
      canvas.drawRRect(
        RRect.fromRectAndRadius(Rect.fromLTWH(x * s, y * s, 8 * s, h * s), Radius.circular(2 * s)),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(_MarkPainter old) => old.bar != bar;
}

/// Marca en la barra lateral: monograma + «Magnus» en la tipografía de marca.
/// Se contrae a solo el monograma cuando [extended] es falso.
class ShellBrand extends StatelessWidget {
  const ShellBrand({super.key, required this.theme, this.extended = true});
  final MagnusTheme theme;
  final bool extended;

  @override
  Widget build(BuildContext context) {
    final t = theme;
    return Padding(
      padding: EdgeInsets.fromLTRB(extended ? 18 : 0, 20, 16, 16),
      child: Row(
        mainAxisAlignment: extended ? MainAxisAlignment.start : MainAxisAlignment.center,
        children: [
          MagnusMark(size: 26, color: t.isDark ? Brand.violet : Brand.violetDeep),
          if (extended) ...[
            const SizedBox(width: 11),
            Flexible(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('Magnus',
                      overflow: TextOverflow.fade,
                      softWrap: false,
                      style: GoogleFonts.bricolageGrotesque(
                          color: t.text,
                          fontSize: 19,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -0.6,
                          height: 1.0)),
                  const SizedBox(height: 3),
                  Text('AGENT OS · BETA',
                      overflow: TextOverflow.fade,
                      softWrap: false,
                      style: TextStyle(
                          color: t.textFaint,
                          fontSize: 9,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 1.6)),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
