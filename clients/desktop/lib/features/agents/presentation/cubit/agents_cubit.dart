import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/error/failures.dart';
import '../../../../core/network/api_models.dart';
import '../../../../core/network/magnus_api.dart';

/// Un paso visible de la ejecución de un agente.
class AgentStep extends Equatable {
  const AgentStep({required this.kind, required this.title, this.detail = ''});
  final String kind; // 'note' | 'tool_call' | 'tool_result'
  final String title;
  final String detail;

  @override
  List<Object?> get props => [kind, title, detail];
}

class AgentsState extends Equatable {
  const AgentsState({
    this.agents = const [],
    this.agentErrors = const {},
    this.skills = const [],
    this.skillErrors = const {},
    this.tools = const [],
    this.models = const [],
    this.collections = const [],
    this.selected,
    this.steps = const [],
    this.answer,
    this.metrics,
    this.running = false,
    this.notice,
    this.error,
  });

  final List<AgentInfo> agents;
  final Map<String, String> agentErrors;
  final List<SkillInfo> skills;
  final Map<String, String> skillErrors;
  final List<ToolInfo> tools;
  final List<LocalModel> models;
  final List<CollectionInfo> collections;
  final String? selected;
  final List<AgentStep> steps;
  final String? answer;
  final TurnMetrics? metrics;
  final bool running;
  final String? notice;
  final String? error;

  AgentInfo? get selectedAgent => agents.where((a) => a.name == selected).firstOrNull;

  AgentsState copyWith({
    List<AgentInfo>? agents,
    Map<String, String>? agentErrors,
    List<SkillInfo>? skills,
    Map<String, String>? skillErrors,
    List<ToolInfo>? tools,
    List<LocalModel>? models,
    List<CollectionInfo>? collections,
    String? selected,
    List<AgentStep>? steps,
    String? answer,
    bool clearAnswer = false,
    TurnMetrics? metrics,
    bool clearMetrics = false,
    bool? running,
    String? notice,
    String? error,
  }) =>
      AgentsState(
        agents: agents ?? this.agents,
        agentErrors: agentErrors ?? this.agentErrors,
        skills: skills ?? this.skills,
        skillErrors: skillErrors ?? this.skillErrors,
        tools: tools ?? this.tools,
        models: models ?? this.models,
        collections: collections ?? this.collections,
        selected: selected ?? this.selected,
        steps: steps ?? this.steps,
        answer: clearAnswer ? null : (answer ?? this.answer),
        metrics: clearMetrics ? null : (metrics ?? this.metrics),
        running: running ?? this.running,
        notice: notice,
        error: error,
      );

  @override
  List<Object?> get props => [
        agents, agentErrors, skills, skillErrors, tools, models, collections, selected,
        steps, answer, metrics, running, notice, error,
      ];
}

/// Agentes (YAML con herramientas) y skills (instrucciones reutilizables).
class AgentsCubit extends Cubit<AgentsState> {
  AgentsCubit(this._api) : super(const AgentsState());

  final MagnusApi _api;

  Future<void> load() async {
    try {
      final (agents, agentErrors) = await _api.agents();
      final (skills, skillErrors) = await _api.skills();
      final tools = await _api.tools();
      final models = (await _api.localModels())
          .where((m) => !m.modelId.contains('embed') && !m.modelId.startsWith('bge'))
          .toList();
      final collections = await _api.collections();
      final selected = agents.any((a) => a.name == state.selected)
          ? state.selected
          : (agents.isEmpty ? null : agents.first.name);
      emit(state.copyWith(
        agents: agents,
        agentErrors: agentErrors,
        skills: skills,
        skillErrors: skillErrors,
        tools: tools,
        models: models,
        collections: collections,
        selected: selected,
      ));
    } on Failure catch (f) {
      emit(state.copyWith(error: f.message));
    }
  }

  void select(String name) {
    if (state.running) return;
    emit(state.copyWith(selected: name, steps: const [], clearAnswer: true, clearMetrics: true));
  }

  Future<void> run(String message, {String? model}) async {
    final agent = state.selectedAgent;
    if (agent == null || message.trim().isEmpty || state.running) return;
    emit(state.copyWith(running: true, steps: const [], clearAnswer: true, clearMetrics: true));
    final steps = <AgentStep>[];
    try {
      await for (final e in _api.runAgent(agent.name, message, model: model)) {
        switch (e['type']) {
          case 'start':
            for (final note in (e['notes'] as List? ?? const [])) {
              steps.add(AgentStep(kind: 'note', title: note.toString()));
            }
          case 'tool_call':
            steps.add(AgentStep(kind: 'tool_call', title: '${e['name']}', detail: '${e['arguments']}'));
          case 'tool_result':
            steps.add(AgentStep(kind: 'tool_result', title: '${e['name']}', detail: '${e['result']}'));
          case 'answer':
            emit(state.copyWith(answer: e['content'] as String?));
          case 'done':
            emit(state.copyWith(
                metrics: TurnMetrics.fromJson((e['metrics'] as Map).cast<String, dynamic>())));
          case 'error':
            emit(state.copyWith(error: e['detail'] as String?));
        }
        emit(state.copyWith(steps: List.of(steps)));
      }
    } on Failure catch (f) {
      emit(state.copyWith(error: f.message));
    }
    emit(state.copyWith(running: false));
  }

  Future<void> saveAgent(AgentInfo agent) async {
    try {
      await _api.saveAgent(agent);
      emit(state.copyWith(selected: agent.name, notice: 'Agente "${agent.name}" guardado.'));
      await load();
    } on Failure catch (f) {
      emit(state.copyWith(error: f.message));
    }
  }

  Future<void> deleteAgent(String name) async {
    try {
      await _api.deleteAgent(name);
      emit(state.copyWith(notice: 'Agente "$name" borrado.'));
      await load();
    } on Failure catch (f) {
      emit(state.copyWith(error: f.message));
    }
  }

  Future<void> saveSkill(String name, String description, String body, List<String> triggers) async {
    try {
      await _api.saveSkill(name, description: description, body: body, triggers: triggers);
      emit(state.copyWith(notice: 'Skill /$name guardada: se aplica desde el siguiente mensaje.'));
      await load();
    } on Failure catch (f) {
      emit(state.copyWith(error: f.message));
    }
  }

  Future<void> deleteSkill(String name) async {
    try {
      await _api.deleteSkill(name);
      emit(state.copyWith(notice: 'Skill /$name borrada.'));
      await load();
    } on Failure catch (f) {
      emit(state.copyWith(error: f.message));
    }
  }

  Future<SkillInfo?> skillDetail(String name) async {
    try {
      return await _api.skill(name);
    } on Failure catch (f) {
      emit(state.copyWith(error: f.message));
      return null;
    }
  }

  void dismiss() => emit(state.copyWith());
}
