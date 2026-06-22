import 'package:flutter/material.dart'
    show Material, Colors, TextField, InputDecoration, OutlineInputBorder;
import 'package:flutter/widgets.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../../core/constants.dart';
import '../../../../core/theme/design_system.dart';
import '../../../../core/theme/magnus_theme.dart';
import '../../../../shared/widgets/ui.dart';
import '../cubit/settings_cubit.dart';

/// Ajustes: diseño nativo, apariencia (claro/oscuro) y URL del daemon.
class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key});
  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  late final TextEditingController _urlCtrl;

  @override
  void initState() {
    super.initState();
    _urlCtrl =
        TextEditingController(text: context.read<SettingsCubit>().state.daemonUrl);
  }

  @override
  void dispose() {
    _urlCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Material(
      color: Colors.transparent,
      child: PageScaffold(
        child: BlocBuilder<SettingsCubit, SettingsState>(
          builder: (context, state) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SectionHeader(
                  icon: LucideIcons.settings,
                  title: 'Ajustes',
                  subtitle: 'Diseño, apariencia y conexión al daemon.',
                ),

                // --- Diseño ---
                GlassCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Sistema de diseño', style: t.h2),
                      const SizedBox(height: 4),
                      Text('Se aplica al instante, sin reiniciar.', style: t.small),
                      const SizedBox(height: 14),
                      Wrap(
                        spacing: 12,
                        runSpacing: 12,
                        children: [
                          for (final d in DesignSystem.values)
                            _DesignOption(
                              design: d,
                              selected: state.design == d,
                              onTap: () =>
                                  context.read<SettingsCubit>().setDesign(d),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),

                // --- Apariencia ---
                GlassCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Apariencia', style: t.h2),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          for (final a in Appearance.values)
                            Padding(
                              padding: const EdgeInsets.only(right: 10),
                              child: _Pressable(
                                onTap: () => context
                                    .read<SettingsCubit>()
                                    .setAppearance(a),
                                child: Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 16, vertical: 10),
                                  decoration: BoxDecoration(
                                    color: state.appearance == a
                                        ? t.accentSoft
                                        : t.surfaceAlt,
                                    borderRadius:
                                        BorderRadius.circular(t.radius),
                                    border: Border.all(
                                        color: state.appearance == a
                                            ? t.accent
                                            : t.stroke),
                                  ),
                                  child: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Icon(
                                          a == Appearance.dark
                                              ? LucideIcons.moon
                                              : LucideIcons.sun,
                                          size: 16,
                                          color: state.appearance == a
                                              ? t.accent
                                              : t.textMuted),
                                      const SizedBox(width: 8),
                                      Text(a.label,
                                          style: t.body.copyWith(
                                              fontWeight: FontWeight.w600,
                                              color: state.appearance == a
                                                  ? t.accent
                                                  : t.text)),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),

                // --- Tipografía ---
                GlassCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Tipografía', style: t.h2),
                      const SizedBox(height: 4),
                      Text('La misma fuente en los tres diseños.', style: t.small),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 10,
                        runSpacing: 10,
                        children: [
                          for (final f in AppConstants.fonts)
                            _Pressable(
                              onTap: () =>
                                  context.read<SettingsCubit>().setFont(f),
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 14, vertical: 10),
                                decoration: BoxDecoration(
                                  color: state.fontFamily == f
                                      ? t.accentSoft
                                      : t.surfaceAlt,
                                  borderRadius: BorderRadius.circular(t.radius),
                                  border: Border.all(
                                      color: state.fontFamily == f
                                          ? t.accent
                                          : t.stroke),
                                ),
                                child: Text(
                                  f,
                                  style: GoogleFonts.getFont(
                                    f, // muestra la fuente misma
                                    fontSize: 14,
                                    fontWeight: FontWeight.w600,
                                    color: state.fontFamily == f
                                        ? t.accent
                                        : t.text,
                                  ),
                                ),
                              ),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),

                // --- Daemon ---
                GlassCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Daemon', style: t.h2),
                      const SizedBox(height: 4),
                      Text('URL de la API local de Magnus.', style: t.small),
                      const SizedBox(height: 14),
                      Row(
                        children: [
                          SizedBox(
                            width: 360,
                            child: TextField(
                              controller: _urlCtrl,
                              style: TextStyle(color: t.text, fontSize: 13.5),
                              decoration: InputDecoration(
                                isDense: true,
                                filled: true,
                                fillColor: t.surfaceAlt,
                                hintText: 'http://127.0.0.1:8420',
                                hintStyle: TextStyle(color: t.textFaint),
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(t.radius),
                                  borderSide: BorderSide(color: t.stroke),
                                ),
                                enabledBorder: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(t.radius),
                                  borderSide: BorderSide(color: t.stroke),
                                ),
                                focusedBorder: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(t.radius),
                                  borderSide: BorderSide(color: t.accent),
                                ),
                              ),
                              onSubmitted: (v) =>
                                  context.read<SettingsCubit>().setDaemonUrl(v),
                            ),
                          ),
                          const SizedBox(width: 12),
                          MagnusButton(
                            label: 'Guardar',
                            icon: LucideIcons.check,
                            onTap: () => context
                                .read<SettingsCubit>()
                                .setDaemonUrl(_urlCtrl.text),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _DesignOption extends StatelessWidget {
  const _DesignOption(
      {required this.design, required this.selected, required this.onTap});
  final DesignSystem design;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return _Pressable(
      onTap: onTap,
      child: Container(
        width: 210,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: selected ? t.accentSoft : t.surfaceAlt,
          borderRadius: BorderRadius.circular(t.radius),
          border: Border.all(
              color: selected ? t.accent : t.stroke, width: selected ? 1.4 : 1),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
              switch (design) {
                DesignSystem.windows => LucideIcons.monitor,
                DesignSystem.material => LucideIcons.smartphone,
                DesignSystem.apple => LucideIcons.laptop,
              },
              size: 20,
              color: selected ? t.accent : t.textMuted,
            ),
            const SizedBox(height: 10),
            Text(design.label,
                style: t.body.copyWith(
                    fontWeight: FontWeight.w700,
                    color: selected ? t.accent : t.text)),
            const SizedBox(height: 2),
            Text(
              switch (design) {
                DesignSystem.windows => 'Fluent · glassmorphism',
                DesignSystem.material => 'Material You',
                DesignSystem.apple => 'macOS · vibrancy',
              },
              style: t.small,
            ),
          ],
        ),
      ),
    );
  }
}

/// Pulsación con feedback.
class _Pressable extends StatefulWidget {
  const _Pressable({required this.child, required this.onTap});
  final Widget child;
  final VoidCallback onTap;
  @override
  State<_Pressable> createState() => _PressableState();
}

class _PressableState extends State<_Pressable> {
  bool _down = false;
  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      child: GestureDetector(
        onTapDown: (_) => setState(() => _down = true),
        onTapCancel: () => setState(() => _down = false),
        onTapUp: (_) => setState(() => _down = false),
        onTap: widget.onTap,
        child: AnimatedScale(
          scale: _down ? 0.98 : 1,
          duration: const Duration(milliseconds: 90),
          child: widget.child,
        ),
      ),
    );
  }
}
