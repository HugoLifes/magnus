import 'package:flutter/widgets.dart';
import 'package:google_fonts/google_fonts.dart';

import 'design_system.dart';

/// Apariencia clara/oscura. Independiente del sistema de diseño.
enum Appearance {
  dark('Oscuro'),
  light('Claro');

  const Appearance(this.label);
  final String label;

  Brightness get brightness =>
      this == Appearance.dark ? Brightness.dark : Brightness.light;

  static Appearance fromName(String? name) => Appearance.values.firstWhere(
        (a) => a.name == name,
        orElse: () => Appearance.dark, // oscuro por defecto: se ve más premium
      );
}

/// Tokens visuales del contenido, **provistos por cada shell** según el diseño
/// elegido (Windows/Material/Apple) y la apariencia (claro/oscuro).
///
/// El contenido de las páginas lee `MagnusTheme.of(context)` y se pinta nativo
/// en cada tema: glassmorphism en Windows, superficies tonales en Material,
/// vibrancy sobria en Apple. Así el contenido es compartido pero con identidad
/// por tema. No depende de Material para poder vivir dentro de Fluent/macos_ui.
@immutable
class MagnusTheme {
  const MagnusTheme({
    required this.design,
    required this.brightness,
    required this.bg,
    required this.surface,
    required this.surfaceStrong,
    required this.surfaceAlt,
    required this.stroke,
    required this.strokeStrong,
    required this.accent,
    required this.accentSoft,
    required this.onAccent,
    required this.ok,
    required this.warn,
    required this.bad,
    required this.info,
    required this.text,
    required this.textMuted,
    required this.textFaint,
    required this.radius,
    required this.radiusLg,
    required this.glass,
    required this.blurSigma,
    required this.shadow,
    required this.uiFamily,
    required this.displayFamily,
  });

  final DesignSystem design;
  final Brightness brightness;

  // Superficies
  final Color bg; // fondo base de la página
  final Color surface; // relleno de tarjeta (translúcido si glass)
  final Color surfaceStrong; // tarjeta destacada / hover
  final Color surfaceAlt; // pistas, tracks, fondos secundarios
  final Color stroke; // bordes hairline
  final Color strokeStrong; // bordes de elementos enfocados/seleccionados

  // Marca / estados
  final Color accent;
  final Color accentSoft; // acento al 12-16% para fondos
  final Color onAccent; // texto sobre acento
  final Color ok;
  final Color warn;
  final Color bad;
  final Color info;

  // Texto
  final Color text;
  final Color textMuted;
  final Color textFaint;

  // Forma / efectos
  final double radius;
  final double radiusLg;
  final bool glass; // usar BackdropFilter en tarjetas
  final double blurSigma;
  final List<BoxShadow> shadow;

  /// Familias tipográficas (Google Fonts). [displayFamily] aporta carácter a
  /// los títulos por tema; [uiFamily] es legible y neutra para el cuerpo.
  final String uiFamily;
  final String displayFamily;

  bool get isDark => brightness == Brightness.dark;

  // --- Tipografía derivada (color desde tokens) ---
  TextStyle get display => GoogleFonts.getFont(displayFamily,
      fontSize: 26,
      height: 1.12,
      fontWeight: FontWeight.w700,
      letterSpacing: -0.5,
      color: text);
  TextStyle get h1 => GoogleFonts.getFont(displayFamily,
      fontSize: 20,
      fontWeight: FontWeight.w600,
      letterSpacing: -0.3,
      color: text);
  TextStyle get h2 => GoogleFonts.getFont(uiFamily,
      fontSize: 15, fontWeight: FontWeight.w600, color: text);
  TextStyle get body => GoogleFonts.getFont(uiFamily,
      fontSize: 13.5, height: 1.45, color: text);
  TextStyle get small => GoogleFonts.getFont(uiFamily,
      fontSize: 12, height: 1.35, fontWeight: FontWeight.w500, color: textMuted);
  TextStyle get mono => GoogleFonts.jetBrainsMono(
      fontSize: 12.5, height: 1.3, color: text);

  // ----------------------------------------------------------------------
  // Fábrica: tokens por (diseño × apariencia).
  // ----------------------------------------------------------------------
  factory MagnusTheme.forDesign(
    DesignSystem design,
    Brightness b, {
    String font = 'Plus Jakarta Sans',
    Color? accent, // acento del sistema (M3 dynamic / Fluent personal)
  }) {
    final dark = b == Brightness.dark;
    final hasA = accent != null;
    // Derivados del acento override (si lo hay).
    final aSoft = hasA
        ? accent.withValues(alpha: dark ? 0.30 : 0.14)
        : null;
    final aOn = hasA
        ? (accent.computeLuminance() > 0.55
            ? const Color(0xFF101018)
            : const Color(0xFFFFFFFF))
        : null;
    switch (design) {
      // ---------------- WINDOWS — glassmorphism (Acrylic/Mica) -------------
      case DesignSystem.windows:
        return MagnusTheme(
          design: design,
          brightness: b,
          uiFamily: font,
          displayFamily: font,
          // Más translúcido + más blur = glass más marcado (lo pedido).
          bg: dark ? const Color(0xFF0B0817) : const Color(0xFFEFEEF9),
          surface: dark ? const Color(0x0FFFFFFF) : const Color(0xB3FFFFFF),
          surfaceStrong:
              dark ? const Color(0x1AFFFFFF) : const Color(0xE6FFFFFF),
          surfaceAlt: dark ? const Color(0x0AFFFFFF) : const Color(0x0A1A1730),
          stroke: dark ? const Color(0x24FFFFFF) : const Color(0x14101030),
          strokeStrong: dark ? const Color(0x4DFFFFFF) : const Color(0x26101030),
          accent: accent ?? (dark ? const Color(0xFF8B7BFF) : const Color(0xFF5A4FCF)),
          accentSoft: aSoft ?? (dark ? const Color(0x308B7BFF) : const Color(0x1A5A4FCF)),
          onAccent: aOn ?? const Color(0xFFFFFFFF),
          ok: const Color(0xFF34D399),
          warn: const Color(0xFFFBBF24),
          bad: const Color(0xFFFB6F92),
          info: const Color(0xFF60C8FF),
          text: dark ? const Color(0xFFECEAFB) : const Color(0xFF1C1930),
          textMuted: dark ? const Color(0xFFB1ADCC) : const Color(0xFF5B5773),
          textFaint: dark ? const Color(0xFF77728F) : const Color(0xFF8C889F),
          radius: 10,
          radiusLg: 16,
          glass: true,
          blurSigma: 40,
          shadow: [
            BoxShadow(
              color: Color(dark ? 0x73000000 : 0x1A000000),
              blurRadius: 36,
              offset: const Offset(0, 16),
            ),
          ],
        );

      // ---------------- MATERIAL — Material You (tonal, sin glass) ---------
      case DesignSystem.material:
        return MagnusTheme(
          design: design,
          brightness: b,
          uiFamily: font,
          displayFamily: font,
          // Material You: superficies tonales con tinte malva, esquinas grandes.
          bg: dark ? const Color(0xFF141218) : const Color(0xFFFEF7FF),
          surface: dark ? const Color(0xFF1D1B20) : const Color(0xFFFFFFFF),
          surfaceStrong:
              dark ? const Color(0xFF2B2930) : const Color(0xFFF7F2FA),
          surfaceAlt: dark ? const Color(0xFF211F26) : const Color(0xFFECE6F0),
          stroke: dark ? const Color(0x1FFFFFFF) : const Color(0x14000000),
          strokeStrong: dark ? const Color(0x3DFFFFFF) : const Color(0x24000000),
          accent: accent ?? (dark ? const Color(0xFFD0BCFF) : const Color(0xFF6750A4)),
          accentSoft: aSoft ?? (dark ? const Color(0x3D6750A4) : const Color(0x166750A4)),
          onAccent: aOn ?? (dark ? const Color(0xFF381E72) : const Color(0xFFFFFFFF)),
          ok: const Color(0xFF4CAF94),
          warn: const Color(0xFFE0A100),
          bad: const Color(0xFFE5484D),
          info: const Color(0xFF4AA8E0),
          text: dark ? const Color(0xFFE6E0E9) : const Color(0xFF1D1B20),
          textMuted: dark ? const Color(0xFFCAC4D0) : const Color(0xFF49454F),
          textFaint: dark ? const Color(0xFF948F99) : const Color(0xFF79747E),
          radius: 18,
          radiusLg: 28,
          glass: false,
          blurSigma: 0,
          shadow: [
            BoxShadow(
              color: Color(dark ? 0x4D000000 : 0x14000000),
              blurRadius: 16,
              offset: const Offset(0, 4),
            ),
          ],
        );

      // ---------------- APPLE — vibrancy sobria (macOS) -------------------
      case DesignSystem.apple:
        return MagnusTheme(
          design: design,
          brightness: b,
          uiFamily: font,
          displayFamily: font,
          bg: dark ? const Color(0xFF1E1E1E) : const Color(0xFFECECEC),
          surface: dark ? const Color(0x14FFFFFF) : const Color(0xF0FFFFFF),
          surfaceStrong:
              dark ? const Color(0x1FFFFFFF) : const Color(0xFFFFFFFF),
          surfaceAlt: dark ? const Color(0x0DFFFFFF) : const Color(0x0F000000),
          stroke: dark ? const Color(0x1AFFFFFF) : const Color(0x14000000),
          strokeStrong: dark ? const Color(0x33FFFFFF) : const Color(0x26000000),
          accent: accent ?? (dark ? const Color(0xFF8E7BFF) : const Color(0xFF6E56CF)),
          accentSoft: aSoft ?? (dark ? const Color(0x268E7BFF) : const Color(0x176E56CF)),
          onAccent: aOn ?? const Color(0xFFFFFFFF),
          ok: const Color(0xFF30D158),
          warn: const Color(0xFFFFD60A),
          bad: const Color(0xFFFF6482),
          info: const Color(0xFF64D2FF),
          text: dark ? const Color(0xFFF5F5F7) : const Color(0xFF1D1D1F),
          textMuted: dark ? const Color(0xFFAEAEB2) : const Color(0xFF6E6E73),
          textFaint: dark ? const Color(0xFF8E8E93) : const Color(0xFF8E8E93),
          radius: 11,
          radiusLg: 16,
          glass: true,
          blurSigma: 18,
          shadow: [
            BoxShadow(
              color: Color(dark ? 0x4D000000 : 0x10000000),
              blurRadius: 22,
              offset: const Offset(0, 10),
            ),
          ],
        );
    }
  }

  // ----------------------------------------------------------------------
  // InheritedWidget para exponerlo en el árbol.
  // ----------------------------------------------------------------------
  static MagnusTheme of(BuildContext context) {
    final scope =
        context.dependOnInheritedWidgetOfExactType<_MagnusThemeScope>();
    assert(scope != null, 'No MagnusTheme en el árbol. Envuelve con MagnusTheme.provide.');
    return scope!.theme;
  }

  /// Envuelve [child] proveyendo este theme a los descendientes.
  Widget provide({required Widget child}) =>
      _MagnusThemeScope(theme: this, child: child);
}

class _MagnusThemeScope extends InheritedWidget {
  const _MagnusThemeScope({required this.theme, required super.child});
  final MagnusTheme theme;

  @override
  bool updateShouldNotify(_MagnusThemeScope old) => old.theme != theme;
}
