import 'package:flutter/widgets.dart';

import '../../../../core/di/injector.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/network/api_models.dart';
import '../../../../core/network/magnus_api.dart';
import '../../../../core/theme/brand.dart';
import '../../../../core/theme/icons.dart';
import '../../../../core/theme/magnus_theme.dart';
import '../../../../shared/widgets/forms.dart';
import '../../../../shared/widgets/ui.dart';

/// Plan de este equipo y activación de la licencia.
///
/// La licencia es un texto firmado que se verifica **sin internet**: se pega
/// aquí y listo. Por eso esta tarjeta nunca consulta a ningún servidor de
/// Magnus, solo al daemon de este equipo.
class LicenseCard extends StatefulWidget {
  const LicenseCard({super.key});

  @override
  State<LicenseCard> createState() => _LicenseCardState();
}

class _LicenseCardState extends State<LicenseCard> {
  final _api = sl<MagnusApi>();
  final _texto = TextEditingController();
  LicenseInfo? _license;
  String? _error;
  String? _ok;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _texto.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final lic = await _api.license();
      if (mounted) setState(() => _license = lic);
    } on Failure catch (f) {
      if (mounted) setState(() => _error = f.message);
    }
  }

  Future<void> _activate() async {
    final texto = _texto.text.trim();
    if (texto.isEmpty) {
      setState(() => _error = 'Pega el texto de la licencia (empieza con MAGNUS1).');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _ok = null;
    });
    try {
      final lic = await _api.activateLicense(texto);
      if (!mounted) return;
      setState(() {
        _license = lic;
        _texto.clear();
        _ok = 'Licencia activada: plan ${lic.plan}.';
      });
    } on Failure catch (f) {
      if (mounted) setState(() => _error = f.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _deactivate() async {
    setState(() => _busy = true);
    try {
      final lic = await _api.deactivateLicense();
      if (mounted) setState(() => _license = lic);
    } on Failure catch (f) {
      if (mounted) setState(() => _error = f.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final lic = _license;
    final pro = lic?.isPro ?? false;
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(pro ? 'Magnus ${_capitalize(lic!.effectivePlan)}' : 'Magnus Pro',
                        style: t.h2),
                    const SizedBox(height: 4),
                    Text(
                      pro
                          ? 'Gracias por apoyar el proyecto.'
                          : 'Hoy usas Community: todo corre en tu equipo, sin pagar tokens.',
                      style: t.small,
                    ),
                  ],
                ),
              ),
              if (lic != null)
                Pill(
                  pro ? _estado(lic) : 'Community',
                  color: pro ? Brand.amber : t.textMuted,
                  icon: pro ? context.icons.success : context.icons.info,
                ),
            ],
          ),
          const SizedBox(height: 16),
          if (!pro) ...[
            const _Ventaja(texto: 'Tus documentos con citas: búsqueda híbrida y evaluación.'),
            const _Ventaja(texto: 'Magnus Code en modo autónomo, con sandbox y puntos de control.'),
            const _Ventaja(texto: 'Índice del repositorio y tareas en segundo plano.'),
            const SizedBox(height: 16),
            Text('¿Ya tienes una licencia o un vale? Pégalo aquí:', style: t.small),
            const SizedBox(height: 8),
            MagnusTextField(
              controller: _texto,
              hint: 'MAGNUS1.…',
              onSubmitted: (_) => _activate(),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                MagnusButton(
                  label: _busy ? 'Activando…' : 'Activar licencia',
                  icon: context.icons.key,
                  onTap: _busy ? null : _activate,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text('Se verifica aquí mismo, sin internet.',
                      style: t.small.copyWith(color: t.textFaint)),
                ),
              ],
            ),
          ] else ...[
            Row(
              children: [
                Icon(context.icons.success, size: 15, color: t.ok),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    [
                      if (lic!.holder.isNotEmpty) lic.holder,
                      if (lic.daysLeft != null) 'quedan ${lic.daysLeft} días',
                      if (lic.daysLeft == null) 'sin vencimiento',
                    ].join(' · '),
                    style: t.small,
                  ),
                ),
                MagnusButton(
                  label: 'Quitar',
                  icon: context.icons.close,
                  primary: false,
                  dense: true,
                  onTap: _busy ? null : _deactivate,
                ),
              ],
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: 10),
            Text(_error!, style: t.small.copyWith(color: t.bad)),
          ],
          if (_ok != null) ...[
            const SizedBox(height: 10),
            Text(_ok!, style: t.small.copyWith(color: t.ok)),
          ],
        ],
      ),
    );
  }

  static String _estado(LicenseInfo lic) =>
      lic.status == 'en gracia' ? 'en gracia' : _capitalize(lic.effectivePlan);

  static String _capitalize(String s) =>
      s.isEmpty ? s : s[0].toUpperCase() + s.substring(1);
}

class _Ventaja extends StatelessWidget {
  const _Ventaja({required this.texto});
  final String texto;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 7),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(context.icons.check, size: 14, color: t.accent),
          const SizedBox(width: 9),
          Expanded(child: Text(texto, style: t.body.copyWith(fontSize: 13))),
        ],
      ),
    );
  }
}
