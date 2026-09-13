import 'package:flutter/material.dart' show SelectableText;
import 'package:flutter/widgets.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../../core/network/api_models.dart';
import '../../../../core/theme/magnus_theme.dart';
import '../../../../shared/format.dart';
import '../../../../shared/widgets/forms.dart';
import '../../../../shared/widgets/ui.dart';
import '../cubit/agents_cubit.dart';

/// Agentes (modelo + instrucciones + herramientas) y skills (instrucciones
/// reutilizables que se activan en el chat con /nombre o por palabras clave).
class AgentsPage extends StatefulWidget {
  const AgentsPage({super.key});
  @override
  State<AgentsPage> createState() => _AgentsPageState();
}

class _AgentsPageState extends State<AgentsPage> {
  int _tab = 0;

  @override
  void initState() {
    super.initState();
    context.read<AgentsCubit>().load();
  }

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<AgentsCubit, AgentsState>(
      builder: (context, state) {
        final cubit = context.read<AgentsCubit>();
        return PageScaffold(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SectionHeader(
                icon: LucideIcons.bot,
                title: 'Agentes y skills',
                subtitle: 'Crea asistentes con herramientas seguras que corren en tu equipo.',
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    ChoiceChipX(
                      label: 'Agentes',
                      icon: LucideIcons.bot,
                      selected: _tab == 0,
                      onTap: () => setState(() => _tab = 0),
                    ),
                    const SizedBox(width: 8),
                    ChoiceChipX(
                      label: 'Skills',
                      icon: LucideIcons.wandSparkles,
                      selected: _tab == 1,
                      onTap: () => setState(() => _tab = 1),
                    ),
                  ],
                ),
              ),
              if (state.error != null) ...[
                InlineNotice(state.error!, onClose: cubit.dismiss),
                const SizedBox(height: 12),
              ],
              if (state.notice != null) ...[
                InlineNotice(state.notice!, kind: NoticeKind.info, onClose: cubit.dismiss),
                const SizedBox(height: 12),
              ],
              if (_tab == 0) _AgentsTab(state: state) else _SkillsTab(state: state),
            ],
          ),
        );
      },
    );
  }
}

// ---------------------------------------------------------------------------
// Agentes
// ---------------------------------------------------------------------------

class _AgentsTab extends StatefulWidget {
  const _AgentsTab({required this.state});
  final AgentsState state;
  @override
  State<_AgentsTab> createState() => _AgentsTabState();
}

class _AgentsTabState extends State<_AgentsTab> {
  final _message = TextEditingController();
  String? _model;
  bool _editing = false;

  @override
  void dispose() {
    _message.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final state = widget.state;
    final cubit = context.read<AgentsCubit>();
    final agent = state.selectedAgent;
    final models = state.models.map((m) => m.modelId).toList();
    final model = _model ?? agent?.model ?? (models.isEmpty ? null : models.first);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(child: Text('Tus agentes', style: t.h2)),
                  MagnusButton(
                    label: _editing ? 'Cerrar editor' : 'Nuevo agente',
                    icon: _editing ? LucideIcons.x : LucideIcons.plus,
                    primary: !_editing,
                    dense: true,
                    onTap: () => setState(() => _editing = !_editing),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final a in state.agents)
                    ChoiceChipX(
                      label: a.builtin ? a.name : '${a.name} · tuyo',
                      icon: LucideIcons.bot,
                      selected: a.name == state.selected,
                      onTap: () {
                        setState(() => _model = null);
                        cubit.select(a.name);
                      },
                    ),
                ],
              ),
              for (final e in state.agentErrors.entries) ...[
                const SizedBox(height: 8),
                InlineNotice('${e.key}: ${e.value}', kind: NoticeKind.warning),
              ],
            ],
          ),
        ),
        if (_editing) ...[
          const SizedBox(height: 16),
          _AgentEditor(
            state: state,
            initial: agent != null && !agent.builtin ? agent : null,
            onSaved: () => setState(() => _editing = false),
          ),
        ],
        if (agent != null) ...[
          const SizedBox(height: 16),
          GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(child: Text(agent.name, style: t.h1)),
                    Pill(agent.builtin ? 'incluido' : 'tuyo', color: agent.builtin ? t.info : t.accent),
                    if (!agent.builtin) ...[
                      const SizedBox(width: 8),
                      MagnusButton(
                        label: 'Borrar',
                        icon: LucideIcons.trash2,
                        primary: false,
                        dense: true,
                        onTap: () => cubit.deleteAgent(agent.name),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 4),
                Text(agent.description, style: t.body),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (final tool in agent.tools) Pill(tool, color: t.accent, icon: LucideIcons.wrench),
                    if (agent.collection != null)
                      Pill(agent.collection!, color: t.info, icon: LucideIcons.bookOpen),
                    Pill('máx. ${agent.maxSteps} pasos', color: t.textMuted),
                  ],
                ),
                const SizedBox(height: 16),
                const FieldLabel('Modelo',
                    hint: 'Para usar herramientas de forma fiable conviene un modelo de 4 B o más.'),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    if (models.isEmpty) Text('Descarga un modelo en la sección Modelos.', style: t.small),
                    for (final m in models)
                      ChoiceChipX(label: m, selected: m == model, onTap: () => setState(() => _model = m)),
                  ],
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    Expanded(
                      child: MagnusTextField(
                        controller: _message,
                        hint: 'Pídele algo al agente…',
                        onSubmitted: (_) => _run(cubit, model),
                      ),
                    ),
                    const SizedBox(width: 10),
                    MagnusButton(
                      label: state.running ? 'Trabajando…' : 'Ejecutar',
                      icon: LucideIcons.play,
                      onTap: state.running || model == null ? null : () => _run(cubit, model),
                    ),
                  ],
                ),
                if (state.steps.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  for (final step in state.steps) _StepRow(step),
                ],
                if (state.answer != null) ...[
                  const SizedBox(height: 12),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: t.surfaceStrong,
                      borderRadius: BorderRadius.circular(t.radiusLg),
                      border: Border.all(color: t.stroke),
                    ),
                    child: SelectableText(state.answer!, style: t.body),
                  ),
                ],
                if (state.metrics != null) ...[
                  const SizedBox(height: 8),
                  Text(
                    '${state.metrics!.tokensOut} tok · ${state.metrics!.durationS.toStringAsFixed(1)} s · '
                    '${formatNum(state.metrics!.avgPowerW, unit: ' W')} · local ${formatUsd(state.metrics!.localCostUsd)} · '
                    '${state.metrics!.cloudReference} ${formatUsd(state.metrics!.cloudCostUsd)}',
                    style: t.small.copyWith(fontSize: 11, color: t.textFaint),
                  ),
                ],
              ],
            ),
          ),
        ],
      ],
    );
  }

  void _run(AgentsCubit cubit, String? model) {
    final text = _message.text.trim();
    if (text.isEmpty || model == null) return;
    cubit.run(text, model: model);
  }
}

class _StepRow extends StatelessWidget {
  const _StepRow(this.step);
  final AgentStep step;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final (icon, color, label) = switch (step.kind) {
      'note' => (LucideIcons.circleAlert, t.warn, step.title),
      'tool_call' => (LucideIcons.wrench, t.accent, 'Usa ${step.title}'),
      _ => (LucideIcons.cornerDownRight, t.ok, 'Resultado de ${step.title}'),
    };
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Icon(icon, size: 15, color: color),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: t.body.copyWith(fontWeight: FontWeight.w600)),
                if (step.detail.isNotEmpty)
                  Text(step.detail,
                      style: t.mono.copyWith(fontSize: 11.5, color: t.textMuted),
                      maxLines: 4,
                      overflow: TextOverflow.ellipsis),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _AgentEditor extends StatefulWidget {
  const _AgentEditor({required this.state, required this.onSaved, this.initial});
  final AgentsState state;
  final AgentInfo? initial;
  final VoidCallback onSaved;

  @override
  State<_AgentEditor> createState() => _AgentEditorState();
}

class _AgentEditorState extends State<_AgentEditor> {
  late final _name = TextEditingController(text: widget.initial?.name ?? '');
  late final _description = TextEditingController(text: widget.initial?.description ?? '');
  late final _system = TextEditingController(text: widget.initial?.system ?? '');
  late String? _model = widget.initial?.model;
  late final Set<String> _tools = {...?widget.initial?.tools};
  late String? _collection = widget.initial?.collection;
  late double _steps = (widget.initial?.maxSteps ?? 6).toDouble();
  late bool _think = widget.initial?.think ?? true;

  @override
  void dispose() {
    _name.dispose();
    _description.dispose();
    _system.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final state = widget.state;
    return GlassCard(
      accentBorder: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(widget.initial == null ? 'Nuevo agente' : 'Editar ${widget.initial!.name}', style: t.h2),
          const SizedBox(height: 14),
          const FieldLabel('Nombre', hint: 'Minúsculas y guiones, p. ej. asistente-ventas.'),
          MagnusTextField(controller: _name, hint: 'mi-agente'),
          const SizedBox(height: 12),
          const FieldLabel('Descripción'),
          MagnusTextField(controller: _description, hint: 'Para qué sirve'),
          const SizedBox(height: 12),
          const FieldLabel('Instrucciones', hint: 'Cómo debe comportarse y cuándo usar cada herramienta.'),
          MagnusTextField(controller: _system, hint: 'Eres…', minLines: 4, maxLines: 10),
          const SizedBox(height: 12),
          const FieldLabel('Herramientas'),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (final tool in state.tools)
                ChoiceChipX(
                  label: tool.name,
                  icon: LucideIcons.wrench,
                  selected: _tools.contains(tool.name),
                  onTap: () => setState(() =>
                      _tools.contains(tool.name) ? _tools.remove(tool.name) : _tools.add(tool.name)),
                ),
            ],
          ),
          const SizedBox(height: 12),
          const FieldLabel('Modelo por omisión'),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              ChoiceChipX(label: 'elegir al ejecutar', selected: _model == null, onTap: () => setState(() => _model = null)),
              for (final m in state.models)
                ChoiceChipX(
                    label: m.modelId, selected: m.modelId == _model, onTap: () => setState(() => _model = m.modelId)),
            ],
          ),
          if (_tools.contains('buscar_documentos')) ...[
            const SizedBox(height: 12),
            const FieldLabel('Colección para buscar_documentos'),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final c in state.collections)
                  ChoiceChipX(
                      label: c.name, selected: c.name == _collection, onTap: () => setState(() => _collection = c.name)),
              ],
            ),
          ],
          const SizedBox(height: 12),
          SliderField(
              label: 'Pasos máximos', value: _steps, min: 1, max: 20, divisions: 19, unit: '',
              onChanged: (v) => setState(() => _steps = v)),
          ToggleField(
            label: 'Razonar antes de actuar',
            hint: 'Más preciso con modelos que razonan; apagado es más rápido.',
            value: _think,
            onChanged: (v) => setState(() => _think = v),
          ),
          const SizedBox(height: 14),
          MagnusButton(
            label: 'Guardar agente',
            icon: LucideIcons.save,
            onTap: () async {
              await context.read<AgentsCubit>().saveAgent(AgentInfo(
                    name: _name.text.trim(),
                    description: _description.text.trim(),
                    system: _system.text.trim(),
                    model: _model,
                    tools: _tools.toList(),
                    collection: _tools.contains('buscar_documentos') ? _collection : null,
                    maxSteps: _steps.round(),
                    think: _think,
                  ));
              widget.onSaved();
            },
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Skills
// ---------------------------------------------------------------------------

class _SkillsTab extends StatefulWidget {
  const _SkillsTab({required this.state});
  final AgentsState state;
  @override
  State<_SkillsTab> createState() => _SkillsTabState();
}

class _SkillsTabState extends State<_SkillsTab> {
  final _name = TextEditingController();
  final _description = TextEditingController();
  final _triggers = TextEditingController();
  final _body = TextEditingController();
  String? _editing;

  @override
  void dispose() {
    for (final c in [_name, _description, _triggers, _body]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _open(SkillInfo skill) async {
    final detail = await context.read<AgentsCubit>().skillDetail(skill.name);
    if (detail == null || !mounted) return;
    setState(() {
      _editing = skill.name;
      _name.text = detail.builtin ? '${detail.name}-mia' : detail.name;
      _description.text = detail.description;
      _triggers.text = detail.triggers.join(', ');
      _body.text = detail.body ?? '';
    });
  }

  void _new() => setState(() {
        _editing = '';
        for (final c in [_name, _description, _triggers, _body]) {
          c.clear();
        }
      });

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final state = widget.state;
    final cubit = context.read<AgentsCubit>();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(child: Text('Skills', style: t.h2)),
                  MagnusButton(label: 'Nueva skill', icon: LucideIcons.plus, dense: true, onTap: _new),
                ],
              ),
              const SizedBox(height: 4),
              Text('En el chat se activan con /nombre al inicio del mensaje o con sus palabras clave.',
                  style: t.small),
              const SizedBox(height: 12),
              for (final s in state.skills)
                GestureDetector(
                  onTap: () => _open(s),
                  child: MouseRegion(
                    cursor: SystemMouseCursors.click,
                    child: Container(
                      margin: const EdgeInsets.only(bottom: 6),
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                      decoration: BoxDecoration(
                        color: _editing == s.name ? t.accentSoft : t.surfaceAlt,
                        borderRadius: BorderRadius.circular(t.radius),
                      ),
                      child: Row(
                        children: [
                          Text('/${s.name}', style: t.mono.copyWith(color: t.accent)),
                          const SizedBox(width: 12),
                          Expanded(child: Text(s.description, style: t.small, maxLines: 2)),
                          Pill(s.builtin ? 'incluida' : 'tuya', color: s.builtin ? t.info : t.accent),
                        ],
                      ),
                    ),
                  ),
                ),
              for (final e in state.skillErrors.entries)
                InlineNotice('${e.key}: ${e.value}', kind: NoticeKind.warning),
            ],
          ),
        ),
        if (_editing != null) ...[
          const SizedBox(height: 16),
          GlassCard(
            accentBorder: true,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(_editing!.isEmpty ? 'Nueva skill' : 'Editar /$_editing', style: t.h2),
                if (_editing!.isNotEmpty &&
                    state.skills.any((s) => s.name == _editing && s.builtin)) ...[
                  const SizedBox(height: 6),
                  Text('Es una skill incluida: se guardará como una copia tuya con otro nombre, '
                      'o con el mismo nombre para reemplazarla.', style: t.small),
                ],
                const SizedBox(height: 12),
                const FieldLabel('Nombre', hint: 'Minúsculas y guiones; se invoca como /nombre.'),
                MagnusTextField(controller: _name, hint: 'correo-formal'),
                const SizedBox(height: 12),
                const FieldLabel('Descripción'),
                MagnusTextField(controller: _description, hint: 'Redacta correos formales'),
                const SizedBox(height: 12),
                const FieldLabel('Palabras clave', hint: 'Separadas por comas.'),
                MagnusTextField(controller: _triggers, hint: 'correo formal, carta'),
                const SizedBox(height: 12),
                const FieldLabel('Instrucciones'),
                MagnusTextField(controller: _body, hint: 'Qué hacer, qué evitar, formato…', minLines: 6, maxLines: 16),
                const SizedBox(height: 14),
                Row(
                  children: [
                    MagnusButton(
                      label: 'Guardar skill',
                      icon: LucideIcons.save,
                      onTap: () => cubit.saveSkill(
                        _name.text.trim(),
                        _description.text.trim(),
                        _body.text,
                        _triggers.text.split(',').map((s) => s.trim()).where((s) => s.isNotEmpty).toList(),
                      ),
                    ),
                    const SizedBox(width: 10),
                    if (state.skills.any((s) => s.name == _name.text.trim() && !s.builtin))
                      MagnusButton(
                        label: 'Borrar',
                        icon: LucideIcons.trash2,
                        primary: false,
                        onTap: () {
                          cubit.deleteSkill(_name.text.trim());
                          setState(() => _editing = null);
                        },
                      ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}
