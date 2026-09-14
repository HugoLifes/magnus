import 'package:flutter/widgets.dart';

/// Colores de marca que NO cambian con la piel (Windows/Material/Apple).
///
/// Cada color tiene un significado y no se usa fuera de él (ver
/// docs/INFORME_PRODUCTO.md §8.2). El verde queda fuera a propósito: es el
/// color de NVIDIA; Magnus vive sobre su hardware pero no se hace pasar por ella.
abstract final class Brand {
  /// Tinta nocturna: fondo de marca.
  static const night = Color(0xFF0E0B1A);

  static const violet = Color(0xFF8B7BFF);
  static const violetDeep = Color(0xFF5A4FCF);
  static const periwinkle = Color(0xFF6D8BFF);
  static const sky = Color(0xFF60C8FF);

  /// Ámbar: SOLO dinero ahorrado y créditos. Si decora, deja de significar.
  static const amber = Color(0xFFF2B441);
  static const amberLight = Color(0xFFFFD68A);

  /// Todo en GPU, paso completado, permiso concedido.
  static const teal = Color(0xFF2DD4BF);

  /// Se desborda a RAM (siempre con rayado).
  static const coral = Color(0xFFFF8A65);

  /// No cabe, error, acción destructiva.
  static const rose = Color(0xFFFB6F92);

  /// Nube: sale del equipo del usuario. No es un error, es una decisión.
  static const lilac = Color(0xFFC4B5FD);

  /// Degradado principal: la aurora violeta → azul → cielo.
  static const auroraColors = [violet, periwinkle, sky];

  static LinearGradient aurora({double opacity = 1}) => LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [for (final c in auroraColors) c.withValues(alpha: opacity)],
      );

  static const savings = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [amber, amberLight],
  );

  /// Color de dónde corrió una respuesta: este equipo, tu red o la nube.
  static Color location(String location) => switch (location) {
        'local' => teal,
        'lan' => sky,
        _ => lilac,
      };
}
