import 'package:flutter/widgets.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/theme/icons.dart';

import '../../../../core/constants.dart';
import '../../../../core/responsive/breakpoints.dart';
import '../../../../core/theme/magnus_theme.dart';
import '../../../../shared/widgets/forms.dart';
import '../../../../shared/widgets/ui.dart';
import '../bloc/models_bloc.dart';
import '../widgets/catalog_view.dart';
import '../widgets/quant_matrix_table.dart';
import '../widgets/serving_config.dart';

/// Modelos: lo que cabe en ESTE equipo (descargar, cargar, liberar) y el
/// análisis de compatibilidad por cuantización para cualquier destino.
class ModelsPage extends StatefulWidget {
  const ModelsPage({super.key});
  @override
  State<ModelsPage> createState() => _ModelsPageState();
}

class _ModelsPageState extends State<ModelsPage> {
  int _tab = 0;

  @override
  void initState() {
    super.initState();
    context.read<ModelsBloc>().add(const ModelsRequested());
  }

  @override
  Widget build(BuildContext context) {
    final compact = Breakpoints.of(context) == ScreenSize.compact;
    final master = _MasterList();
    final detail = _DetailPanel();

    return PageScaffold(
      scroll: false,
      padding: const EdgeInsets.fromLTRB(28, 26, 28, 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeader(
            icon: context.icons.gpu,
            eyebrow: 'Catálogo',
            title: 'Modelos',
            subtitle: 'Descarga y carga modelos en tu hardware, o analiza la memoria que necesitan.',
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                ChoiceChipX(
                  label: 'Para este equipo',
                  icon: context.icons.sparkle,
                  selected: _tab == 0,
                  onTap: () => setState(() => _tab = 0),
                ),
                const SizedBox(width: 8),
                ChoiceChipX(
                  label: 'Compatibilidad',
                  icon: context.icons.calculator,
                  selected: _tab == 1,
                  onTap: () => setState(() => _tab = 1),
                ),
              ],
            ),
          ),
          Expanded(
            child: _tab == 0
                ? const CatalogView()
                : compact
                    ? ListView(children: [
                        SizedBox(height: 260, child: master),
                        const SizedBox(height: 16),
                        detail,
                      ])
                    : Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          SizedBox(width: 290, child: master),
                          const SizedBox(width: 20),
                          Expanded(child: SingleChildScrollView(child: detail)),
                        ],
                      ),
          ),
        ],
      ),
    );
  }
}

class _MasterList extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return BlocBuilder<ModelsBloc, ModelsState>(
      builder: (context, state) {
        if (state.modelsStatus == Status.loading ||
            state.modelsStatus == Status.initial) {
          return GlassCard(child: Text('Cargando modelos…', style: t.small));
        }
        if (state.modelsStatus == Status.failure) {
          return GlassCard(
            child: Text(state.failureMessage ?? 'Error',
                style: t.body.copyWith(color: t.bad)),
          );
        }
        return GlassCard(
          padding: const EdgeInsets.all(10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(8, 6, 8, 10),
                child: Text('Registro · ${state.models.length}', style: t.small),
              ),
              Expanded(
                child: ListView.separated(
                  itemCount: state.models.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 4),
                  itemBuilder: (context, i) {
                    final m = state.models[i];
                    final selected = m.id == state.selectedModelId;
                    return _Pressable(
                      onTap: () =>
                          context.read<ModelsBloc>().add(ModelSelected(m.id)),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 10),
                        decoration: BoxDecoration(
                          color: selected ? t.accentSoft : const Color(0x00000000),
                          borderRadius: BorderRadius.circular(t.radius),
                          border: Border.all(
                              color: selected ? t.accent.withValues(alpha: 0.4)
                                  : const Color(0x00000000)),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(m.id,
                                style: t.body.copyWith(
                                    fontWeight: FontWeight.w600,
                                    color: selected ? t.accent : t.text)),
                            const SizedBox(height: 2),
                            Text('${m.paramsB}B · ${m.architecture}',
                                style: t.small),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _DetailPanel extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return BlocBuilder<ModelsBloc, ModelsState>(
      builder: (context, state) {
        if (state.selectedModelId == null) {
          return EmptyState(
            icon: context.icons.choose,
            title: 'Selecciona un modelo',
            message:
                'Elige un modelo del registro para ver cuánta memoria necesita '
                'en cada cuantización y en qué hardware cabe.',
          );
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            GlassCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(state.selectedModelId!,
                      style: t.h1, maxLines: 1, overflow: TextOverflow.ellipsis),
                  const SizedBox(height: 16),
                  Text('Destino de hardware', style: t.h2),
                  const SizedBox(height: 10),
                  _TargetChips(selected: state.selectedTarget),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Text('Compatibilidad por cuantización', style: t.h2),
            const SizedBox(height: 4),
            Text('VRAM requerida y runtimes válidos en el destino elegido.',
                style: t.small),
            const SizedBox(height: 12),
            switch (state.matrixStatus) {
              Status.loading =>
                GlassCard(child: Text('Calculando matriz…', style: t.small)),
              Status.failure => GlassCard(
                  child: Text(state.failureMessage ?? 'Error',
                      style: t.body.copyWith(color: t.bad))),
              Status.success => QuantMatrixTable(rows: state.matrix),
              Status.initial => const SizedBox.shrink(),
            },
            const SizedBox(height: 16),
            ServingConfigCard(gpus: state.gpus),
          ],
        );
      },
    );
  }
}

class _TargetChips extends StatelessWidget {
  const _TargetChips({required this.selected});
  final String selected;
  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final target in AppConstants.targets)
          ChoiceChipX(
            label: target,
            selected: target == selected,
            onTap: () => context.read<ModelsBloc>().add(TargetSelected(target)),
          ),
      ],
    );
  }
}

/// Pulsación con feedback (local para evitar exponer el de ui.dart).
class _Pressable extends StatefulWidget {
  const _Pressable({required this.child, this.onTap});
  final Widget child;
  final VoidCallback? onTap;
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
        behavior: HitTestBehavior.opaque,
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
