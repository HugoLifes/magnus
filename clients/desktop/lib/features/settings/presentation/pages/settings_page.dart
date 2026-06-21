import 'package:flutter/material.dart' show Material, Colors, TextField, InputDecoration, OutlineInputBorder;
import 'package:flutter/widgets.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/theme/design_system.dart';
import '../../../models/presentation/widgets/ui_tokens.dart';
import '../cubit/settings_cubit.dart';

/// Ajustes: elegir entre los 3 diseños nativos y configurar la URL del daemon.
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
    _urlCtrl = TextEditingController(text: context.read<SettingsCubit>().state.daemonUrl);
  }

  @override
  void dispose() {
    _urlCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Material transparente: habilita inputs Material dentro de cualquier shell.
    return Material(
      color: Colors.transparent,
      child: BlocBuilder<SettingsCubit, SettingsState>(
        builder: (context, state) {
          return SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Ajustes', style: T.h1),
                const SizedBox(height: 24),
                const Text('Diseño', style: T.h2),
                const SizedBox(height: 4),
                const Text('Elige el sistema de diseño nativo. Se aplica al instante.', style: T.small),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: [
                    for (final d in DesignSystem.values)
                      _DesignOption(
                        design: d,
                        selected: state.design == d,
                        onTap: () => context.read<SettingsCubit>().setDesign(d),
                      ),
                  ],
                ),
                const SizedBox(height: 28),
                const Text('Daemon', style: T.h2),
                const SizedBox(height: 4),
                const Text('URL de la API local de Magnus.', style: T.small),
                const SizedBox(height: 12),
                SizedBox(
                  width: 380,
                  child: TextField(
                    controller: _urlCtrl,
                    decoration: const InputDecoration(
                      isDense: true,
                      border: OutlineInputBorder(),
                      hintText: 'http://127.0.0.1:8420',
                    ),
                    onSubmitted: (v) => context.read<SettingsCubit>().setDaemonUrl(v),
                  ),
                ),
                const SizedBox(height: 8),
                GestureDetector(
                  onTap: () => context.read<SettingsCubit>().setDaemonUrl(_urlCtrl.text),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    decoration: BoxDecoration(color: T.accent, borderRadius: BorderRadius.circular(8)),
                    child: const Text('Guardar', style: TextStyle(color: Color(0xFFFFFFFF), fontWeight: FontWeight.w600)),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _DesignOption extends StatelessWidget {
  const _DesignOption({required this.design, required this.selected, required this.onTap});
  final DesignSystem design;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 200,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: selected ? T.accent : T.card,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: selected ? T.accent : T.line, width: selected ? 2 : 1),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(design.label,
                style: T.body.copyWith(
                    fontWeight: FontWeight.w700,
                    color: selected ? const Color(0xFFFFFFFF) : T.ink)),
            const SizedBox(height: 4),
            Text(
              switch (design) {
                DesignSystem.windows => 'Fluent / WinUI',
                DesignSystem.material => 'Material 3',
                DesignSystem.apple => 'macOS nativo',
              },
              style: TextStyle(fontSize: 11, color: selected ? const Color(0xFFE6E4F7) : T.muted),
            ),
          ],
        ),
      ),
    );
  }
}
