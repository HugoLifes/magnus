import 'package:flutter/material.dart'
    show Material, Colors, TextField, InputDecoration, OutlineInputBorder;
import 'package:flutter/widgets.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/theme/icons.dart';

import '../../../../core/theme/magnus_theme.dart';
import '../../../../shared/widgets/ui.dart';
import '../cubit/settings_cubit.dart';

/// Token de acceso del daemon. Solo hace falta si el daemon escucha en la red
/// (`magnus token new` + `magnus serve --host 0.0.0.0`).
class DaemonTokenField extends StatefulWidget {
  const DaemonTokenField({super.key});
  @override
  State<DaemonTokenField> createState() => _DaemonTokenFieldState();
}

class _DaemonTokenFieldState extends State<DaemonTokenField> {
  final _ctrl = TextEditingController();

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final cubit = context.read<SettingsCubit>();
    final hasToken = context.select((SettingsCubit c) => c.state.hasToken);
    OutlineInputBorder border(Color c) => OutlineInputBorder(
          borderRadius: BorderRadius.circular(t.radius),
          borderSide: BorderSide(color: c),
        );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text('Token de acceso', style: t.body.copyWith(fontWeight: FontWeight.w600)),
            const SizedBox(width: 8),
            Pill(hasToken ? 'configurado' : 'sin token', color: hasToken ? t.ok : t.textFaint),
          ],
        ),
        Text('Solo si el daemon está en otra máquina y escucha en la red.', style: t.small),
        const SizedBox(height: 10),
        Row(
          children: [
            SizedBox(
              width: 360,
              child: Material(
                color: Colors.transparent,
                child: TextField(
                  controller: _ctrl,
                  obscureText: true,
                  style: TextStyle(color: t.text, fontSize: 13.5),
                  decoration: InputDecoration(
                    isDense: true,
                    filled: true,
                    fillColor: t.surfaceAlt,
                    hintText: hasToken ? '•••••••• (pega uno nuevo para cambiarlo)' : 'Pega el token',
                    hintStyle: TextStyle(color: t.textFaint),
                    border: border(t.stroke),
                    enabledBorder: border(t.stroke),
                    focusedBorder: border(t.accent),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            MagnusButton(
              label: 'Guardar token',
              icon: context.icons.key,
              onTap: () {
                cubit.setDaemonToken(_ctrl.text);
                _ctrl.clear();
              },
            ),
            if (hasToken) ...[
              const SizedBox(width: 8),
              MagnusButton(
                label: 'Quitar',
                primary: false,
                onTap: () => cubit.setDaemonToken(''),
              ),
            ],
          ],
        ),
      ],
    );
  }
}
