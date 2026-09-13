import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/error/failures.dart';
import '../../../../core/network/api_models.dart';
import '../../../../core/network/magnus_api.dart';

/// Un mensaje en pantalla. El del asistente se va llenando token a token.
class ChatBubble extends Equatable {
  const ChatBubble({
    required this.role,
    this.text = '',
    this.thinking = '',
    this.metrics,
    this.skills = const [],
    this.sources = const [],
    this.streaming = false,
    this.error,
  });

  final String role; // 'user' | 'assistant'
  final String text;
  final String thinking;
  final TurnMetrics? metrics;
  final List<String> skills;
  final List<String> sources;
  final bool streaming;
  final String? error;

  bool get isUser => role == 'user';

  ChatBubble copyWith({
    String? text,
    String? thinking,
    TurnMetrics? metrics,
    List<String>? skills,
    List<String>? sources,
    bool? streaming,
    String? error,
  }) =>
      ChatBubble(
        role: role,
        text: text ?? this.text,
        thinking: thinking ?? this.thinking,
        metrics: metrics ?? this.metrics,
        skills: skills ?? this.skills,
        sources: sources ?? this.sources,
        streaming: streaming ?? this.streaming,
        error: error ?? this.error,
      );

  @override
  List<Object?> get props => [role, text, thinking, metrics, skills, sources, streaming, error];
}

class ChatState extends Equatable {
  const ChatState({
    this.conversations = const [],
    this.activeId,
    this.messages = const [],
    this.models = const [],
    this.model,
    this.collections = const [],
    this.collection,
    this.think,
    this.sending = false,
    this.loading = false,
    this.error,
  });

  final List<ConversationInfo> conversations;
  final String? activeId;
  final List<ChatBubble> messages;
  final List<LocalModel> models;
  final String? model;
  final List<CollectionInfo> collections;
  final String? collection;

  /// Razonamiento: null = el del modelo, false = apagado (más rápido).
  final bool? think;
  final bool sending;
  final bool loading;
  final String? error;

  /// Coste y ahorro acumulados de la conversación abierta.
  double get savings => messages.fold(0, (s, m) => s + (m.metrics?.savingsUsd ?? 0));
  int get tokens =>
      messages.fold(0, (s, m) => s + (m.metrics?.tokensIn ?? 0) + (m.metrics?.tokensOut ?? 0));

  ChatState copyWith({
    List<ConversationInfo>? conversations,
    String? activeId,
    bool clearActive = false,
    List<ChatBubble>? messages,
    List<LocalModel>? models,
    String? model,
    List<CollectionInfo>? collections,
    String? collection,
    bool clearCollection = false,
    bool? think,
    bool clearThink = false,
    bool? sending,
    bool? loading,
    String? error,
  }) =>
      ChatState(
        conversations: conversations ?? this.conversations,
        activeId: clearActive ? null : (activeId ?? this.activeId),
        messages: messages ?? this.messages,
        models: models ?? this.models,
        model: model ?? this.model,
        collections: collections ?? this.collections,
        collection: clearCollection ? null : (collection ?? this.collection),
        think: clearThink ? null : (think ?? this.think),
        sending: sending ?? this.sending,
        loading: loading ?? this.loading,
        error: error,
      );

  @override
  List<Object?> get props => [
        conversations, activeId, messages, models, model, collections, collection,
        think, sending, loading, error,
      ];
}

/// Chat: conversaciones guardadas en el daemon + turno por WebSocket con
/// tokens en vivo, razonamiento aparte, fuentes del RAG y medidor por respuesta.
class ChatCubit extends Cubit<ChatState> {
  ChatCubit(this._api) : super(const ChatState());

  final MagnusApi _api;

  Future<void> load() async {
    emit(state.copyWith(loading: true));
    try {
      final results = await Future.wait([
        _api.conversations(),
        _api.localModels(),
        _api.collections(),
      ]);
      final models = results[1] as List<LocalModel>;
      final chatModels =
          models.where((m) => !m.modelId.contains('embed') && !m.modelId.startsWith('bge')).toList();
      final keep = chatModels.any((m) => m.modelId == state.model);
      emit(state.copyWith(
        loading: false,
        conversations: results[0] as List<ConversationInfo>,
        models: chatModels,
        model: keep ? state.model : (chatModels.isEmpty ? null : chatModels.first.modelId),
        collections: results[2] as List<CollectionInfo>,
      ));
    } on Failure catch (f) {
      emit(state.copyWith(loading: false, error: f.message));
    }
  }

  Future<void> open(String id) async {
    if (state.sending) return;
    emit(state.copyWith(activeId: id, messages: const [], loading: true));
    try {
      final stored = await _api.conversationMessages(id);
      emit(state.copyWith(
        loading: false,
        messages: [
          for (final m in stored)
            ChatBubble(role: m.role, text: m.content, metrics: m.metrics),
        ],
      ));
    } on Failure catch (f) {
      emit(state.copyWith(loading: false, error: f.message));
    }
  }

  void newConversation() {
    if (state.sending) return;
    emit(state.copyWith(clearActive: true, messages: const []));
  }

  void selectModel(String model) => emit(state.copyWith(model: model));

  void selectCollection(String? name) => name == null
      ? emit(state.copyWith(clearCollection: true))
      : emit(state.copyWith(collection: name));

  void setThink(bool? value) =>
      value == null ? emit(state.copyWith(clearThink: true)) : emit(state.copyWith(think: value));

  void dismissError() => emit(state.copyWith());

  Future<void> delete(String id) async {
    try {
      await _api.deleteConversation(id);
      if (state.activeId == id) newConversation();
      emit(state.copyWith(conversations: state.conversations.where((c) => c.id != id).toList()));
    } on Failure catch (f) {
      emit(state.copyWith(error: f.message));
    }
  }

  void _updateLast(ChatBubble Function(ChatBubble) change) {
    final messages = [...state.messages];
    messages[messages.length - 1] = change(messages.last);
    emit(state.copyWith(messages: messages));
  }

  Future<void> send(String text) async {
    final message = text.trim();
    if (message.isEmpty || state.sending) return;
    final model = state.model;
    if (model == null) {
      emit(state.copyWith(
          error: 'No hay modelos descargados. Descarga uno en la sección Modelos.'));
      return;
    }
    emit(state.copyWith(
      sending: true,
      messages: [
        ...state.messages,
        ChatBubble(role: 'user', text: message),
        const ChatBubble(role: 'assistant', streaming: true),
      ],
    ));

    try {
      await for (final event in _api.chatTurn({
        'model': model,
        'message': message,
        if (state.activeId != null) 'conversation_id': state.activeId,
        if (state.collection != null) 'collection': state.collection,
        if (state.think != null) 'think': state.think,
      })) {
        switch (event['type']) {
          case 'start':
            final sources = (event['sources'] as List? ?? const [])
                .map((s) => '[${(s as Map)['n']}] ${s['title']}')
                .toList();
            final skills = (event['skills'] as List? ?? const []).map((s) => '/$s').toList();
            emit(state.copyWith(activeId: event['conversation_id'] as String?));
            _updateLast((b) => b.copyWith(skills: skills, sources: sources));
          case 'thinking':
            _updateLast((b) => b.copyWith(thinking: b.thinking + (event['content'] as String)));
          case 'token':
            _updateLast((b) => b.copyWith(text: b.text + (event['content'] as String)));
          case 'done':
            _updateLast((b) => b.copyWith(
                  streaming: false,
                  text: event['content'] as String? ?? b.text,
                  metrics: TurnMetrics.fromJson((event['metrics'] as Map).cast<String, dynamic>()),
                ));
          case 'error':
            _updateLast((b) => b.copyWith(streaming: false, error: event['detail'] as String?));
        }
      }
    } on Failure catch (f) {
      _updateLast((b) => b.copyWith(streaming: false, error: f.message));
    } finally {
      final last = state.messages.last;
      if (last.streaming) _updateLast((b) => b.copyWith(streaming: false));
      emit(state.copyWith(sending: false));
    }

    // La lista de la izquierda gana el título de la conversación nueva.
    try {
      emit(state.copyWith(conversations: await _api.conversations()));
    } on Failure {
      // no bloquea el chat
    }
  }
}
