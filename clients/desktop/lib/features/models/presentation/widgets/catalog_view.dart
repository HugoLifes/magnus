import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/theme/icons.dart';

import '../../../../core/network/api_models.dart';
import '../../../../core/theme/magnus_theme.dart';
import '../../../../shared/format.dart';
import '../../../../shared/widgets/forms.dart';
import '../../../../shared/widgets/ui.dart';
import '../cubit/catalog_cubit.dart';

const _capabilities = {
  'chat': 'Chat',
  'code': 'Código',
  'reasoning': 'Razonamiento',
  'vision': 'Visión',
  'tools': 'Herramientas',
  'embedding': 'Embeddings',
};

/// Modelos que caben en ESTE equipo, con descarga, carga y liberación.
class CatalogView extends StatefulWidget {
  const CatalogView({super.key});
  @override
  State<CatalogView> createState() => _CatalogViewState();
}

class _CatalogViewState extends State<CatalogView> {
  @override
  void initState() {
    super.initState();
    context.read<CatalogCubit>().load();
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return BlocBuilder<CatalogCubit, CatalogState>(
      builder: (context, state) {
        final cubit = context.read<CatalogCubit>();
        final catalog = state.catalog;
        return ListView(
          children: [
            Wrap(
              spacing: 6,
              runSpacing: 6,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                if (catalog != null)
                  Pill('${catalog.usableGib.toStringAsFixed(1)} GiB utilizables',
                      color: t.accent, icon: context.icons.memory),
                const SizedBox(width: 8),
                ChoiceChipX(
                  label: 'Todos',
                  selected: state.capability == null,
                  onTap: () => cubit.setCapability(null),
                ),
                for (final entry in _capabilities.entries)
                  ChoiceChipX(
                    label: entry.value,
                    selected: state.capability == entry.key,
                    onTap: () => cubit.setCapability(entry.key),
                  ),
                const SizedBox(width: 8),
                MagnusButton(
                  label: 'Actualizar',
                  icon: context.icons.refresh,
                  primary: false,
                  dense: true,
                  onTap: state.loading ? null : cubit.load,
                ),
              ],
            ),
            const SizedBox(height: 14),
            if (state.error != null) ...[
              InlineNotice(state.error!, onClose: cubit.dismiss),
              const SizedBox(height: 10),
            ],
            if (state.notice != null) ...[
              InlineNotice(state.notice!, kind: NoticeKind.info, onClose: cubit.dismiss),
              const SizedBox(height: 10),
            ],
            Text('Descargados', style: t.h2),
            const SizedBox(height: 10),
            if (state.local.isEmpty)
              GlassCard(
                child: Text(
                    state.loading ? 'Cargando…' : 'Aún no hay modelos descargados. Elige uno abajo.',
                    style: t.small),
              )
            else
              GlassCard(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                child: Column(
                  children: [
                    for (final m in state.local) _LocalRow(model: m, state: state),
                  ],
                ),
              ),
            const SizedBox(height: 22),
            Text('Recomendados para este equipo', style: t.h2),
            const SizedBox(height: 4),
            Text('Ordenados del más capaz al menor entre los que caben.', style: t.small),
            const SizedBox(height: 12),
            if (catalog == null)
              GlassCard(child: Text(state.loading ? 'Cargando catálogo…' : 'Sin catálogo.', style: t.small))
            else
              TileGrid(
                minTileWidth: 290,
                children: [
                  for (final entry in catalog.models) _CatalogCard(entry: entry, state: state),
                ],
              ),
          ],
        );
      },
    );
  }
}

class _LocalRow extends StatelessWidget {
  const _LocalRow({required this.model, required this.state});
  final LocalModel model;
  final CatalogState state;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final cubit = context.read<CatalogCubit>();
    final id = model.modelId;
    final loaded = state.isLoaded(id);
    final busy = state.busy.contains(id);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          StatusDot(loaded ? t.ok : t.textFaint),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(id, style: t.body.copyWith(fontWeight: FontWeight.w600)),
                Text(
                  [
                    formatGib(model.sizeGib),
                    if (model.parameterSize != null) model.parameterSize!,
                    if (model.quantization != null) model.quantization!,
                    loaded ? 'cargado' : 'en disco',
                  ].join(' · '),
                  style: t.small,
                ),
              ],
            ),
          ),
          if (busy)
            Text('trabajando…', style: t.small)
          else ...[
            loaded
                ? MagnusButton(
                    label: 'Liberar',
                    icon: context.icons.unload,
                    primary: false,
                    dense: true,
                    onTap: () => cubit.unloadModel(id),
                  )
                : MagnusButton(
                    label: 'Cargar',
                    icon: context.icons.play,
                    dense: true,
                    onTap: () => cubit.loadModel(id),
                  ),
            const SizedBox(width: 8),
            _ConfirmButton(label: 'Borrar', onConfirm: () => cubit.deleteModel(id)),
          ],
        ],
      ),
    );
  }
}

class _CatalogCard extends StatelessWidget {
  const _CatalogCard({required this.entry, required this.state});
  final CatalogEntry entry;
  final CatalogState state;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final cubit = context.read<CatalogCubit>();
    final pull = state.pulls[entry.id];
    final local = state.isLocal(entry.id);
    final (verdict, color) = entry.fits
        ? ('Cabe', t.ok)
        : (entry.note != null ? ('Lento', t.warn) : ('No cabe', t.bad));
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(entry.name, style: t.h2)),
              Pill(verdict, color: color),
            ],
          ),
          const SizedBox(height: 2),
          Text(entry.id, style: t.mono.copyWith(fontSize: 11.5, color: t.textMuted)),
          const SizedBox(height: 8),
          Text(entry.description, style: t.small, maxLines: 3, overflow: TextOverflow.ellipsis),
          const SizedBox(height: 10),
          Wrap(
            spacing: 5,
            runSpacing: 5,
            children: [
              for (final c in entry.capabilities) Pill(_capabilities[c] ?? c, color: t.info),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            '${entry.paramsB} B · descarga ${entry.sizeGib} GiB · necesita ${entry.requiredGib} GiB · ${entry.license}',
            style: t.small.copyWith(fontSize: 11, color: t.textFaint),
          ),
          if (entry.note != null) ...[
            const SizedBox(height: 6),
            Text(entry.note!, style: t.small.copyWith(color: t.warn)),
          ],
          const SizedBox(height: 12),
          if (pull != null) ...[
            UsageBar(fraction: (pull.percent ?? 0) / 100, color: t.accent),
            const SizedBox(height: 6),
            Text(
              pull.percent == null
                  ? pull.status
                  : '${pull.percent!.toStringAsFixed(0)} % · ${formatBytes(pull.completed)} de ${formatBytes(pull.total)}',
              style: t.small,
            ),
          ] else if (local)
            Row(
              children: [
                Icon(context.icons.success, size: 15, color: t.ok),
                const SizedBox(width: 6),
                Text('Descargado', style: t.small.copyWith(color: t.ok)),
              ],
            )
          else
            MagnusButton(
              label: 'Descargar',
              icon: context.icons.download,
              primary: entry.fits,
              dense: true,
              onTap: () => cubit.pull(entry.id),
            ),
        ],
      ),
    );
  }
}

/// Botón destructivo en dos pasos: el primer toque pide confirmación.
class _ConfirmButton extends StatefulWidget {
  const _ConfirmButton({required this.label, required this.onConfirm});
  final String label;
  final VoidCallback onConfirm;

  @override
  State<_ConfirmButton> createState() => _ConfirmButtonState();
}

class _ConfirmButtonState extends State<_ConfirmButton> {
  bool _armed = false;
  Timer? _timer;

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _tap() {
    if (_armed) {
      _timer?.cancel();
      setState(() => _armed = false);
      widget.onConfirm();
      return;
    }
    setState(() => _armed = true);
    _timer = Timer(const Duration(seconds: 3), () {
      if (mounted) setState(() => _armed = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    return MagnusButton(
      label: _armed ? '¿Seguro?' : widget.label,
      icon: context.icons.delete,
      primary: _armed,
      dense: true,
      onTap: _tap,
    );
  }
}
