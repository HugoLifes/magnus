import 'package:flutter/widgets.dart';

import '../../../../core/di/injector.dart';
import '../../../../core/error/failures.dart';
import '../../../../core/network/api_models.dart';
import '../../../../core/network/magnus_api.dart';
import '../../../../core/theme/icons.dart';
import '../../../../core/theme/magnus_theme.dart';
import '../../../../shared/widgets/ui.dart';

/// Cómo habla Magnus en el chat.
///
/// Vive en el daemon (no en la app) porque la personalidad va en el prompt de
/// cada turno: así vale igual desde la app, desde `magnus chat` o desde
/// cualquier cliente conectado a este equipo.
class PersonaCard extends StatefulWidget {
  const PersonaCard({super.key});

  @override
  State<PersonaCard> createState() => _PersonaCardState();
}

class _PersonaCardState extends State<PersonaCard> {
  final _api = sl<MagnusApi>();
  List<PersonaInfo> _personas = const [];
  String _selected = 'magnus';
  String? _error;
  bool _loaded = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final personas = await _api.personas();
      final settings = await _api.daemonSettings();
      if (!mounted) return;
      setState(() {
        _personas = personas;
        _selected = settings.persona;
        _loaded = true;
        _error = null;
      });
    } on Failure catch (f) {
      if (mounted) setState(() => _error = f.message);
    }
  }

  Future<void> _select(String id) async {
    final anterior = _selected;
    setState(() => _selected = id); // respuesta inmediata; se revierte si falla
    try {
      await _api.updateDaemonSettings({'persona': id});
    } on Failure catch (f) {
      if (!mounted) return;
      setState(() {
        _selected = anterior;
        _error = f.message;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Personalidad', style: t.h2),
          const SizedBox(height: 4),
          Text('Cómo te habla Magnus. Vale para el chat de la app y para la terminal.',
              style: t.small),
          const SizedBox(height: 14),
          if (_error != null)
            Text(_error!, style: t.small.copyWith(color: t.bad))
          else if (!_loaded)
            Text('Cargando…', style: t.small)
          else
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                for (final p in _personas)
                  _PersonaChip(
                    persona: p,
                    selected: p.id == _selected,
                    onTap: () => _select(p.id),
                  ),
              ],
            ),
          if (_loaded && _error == null) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                Icon(context.icons.tip, size: 14, color: t.textFaint),
                const SizedBox(width: 7),
                Expanded(
                  child: Text(
                    'En modelos pequeños Magnus acorta sus instrucciones solo, para no '
                    'gastarles el contexto.',
                    style: t.small.copyWith(color: t.textFaint),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _PersonaChip extends StatelessWidget {
  const _PersonaChip({required this.persona, required this.selected, required this.onTap});

  final PersonaInfo persona;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return GestureDetector(
      onTap: onTap,
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 140),
          width: 176,
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            color: selected ? t.accentSoft : t.surfaceAlt,
            borderRadius: BorderRadius.circular(t.radius),
            border: Border.all(color: selected ? t.accent : t.stroke, width: selected ? 1.4 : 1),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(selected ? context.icons.success : context.icons.chat,
                      size: 15, color: selected ? t.accent : t.textMuted),
                  const SizedBox(width: 8),
                  Text(persona.name,
                      style: t.h2.copyWith(
                          fontSize: 14, color: selected ? t.text : t.textMuted)),
                ],
              ),
              const SizedBox(height: 4),
              Text(persona.tagline, style: t.small.copyWith(fontSize: 11.5)),
            ],
          ),
        ),
      ),
    );
  }
}
