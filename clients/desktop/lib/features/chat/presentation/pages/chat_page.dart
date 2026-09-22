import 'package:flutter/material.dart'
    show Material, Colors, TextField, InputDecoration, InputBorder, SelectableText;
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/theme/icons.dart';

import '../../../../core/network/api_models.dart';
import '../../../../core/responsive/breakpoints.dart';
import '../../../../core/theme/brand.dart';
import '../../../../core/theme/magnus_theme.dart';
import '../../../../shared/format.dart';
import '../../../../shared/widgets/forms.dart';
import '../../../../shared/widgets/markdown.dart';
import '../../../../shared/widgets/magnus_kit.dart';
import '../../../../shared/widgets/ui.dart';
import '../cubit/chat_cubit.dart';

/// Chat: historial guardado en el daemon + hilo con tokens en vivo, skills,
/// fuentes de documentos y el medidor de coste de cada respuesta.
class ChatPage extends StatefulWidget {
  const ChatPage({super.key});
  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final _input = TextEditingController();
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    context.read<ChatCubit>().load();
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _send() {
    final text = _input.text;
    if (text.trim().isEmpty) return;
    _input.clear();
    context.read<ChatCubit>().send(text);
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.jumpTo(_scroll.position.maxScrollExtent);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final compact = Breakpoints.of(context) == ScreenSize.compact;
    return Material(
      color: Colors.transparent,
      child: BlocConsumer<ChatCubit, ChatState>(
        listenWhen: (a, b) => a.messages != b.messages,
        listener: (_, __) => _scrollToEnd(),
        builder: (context, state) => Padding(
          padding: const EdgeInsets.fromLTRB(20, 22, 20, 20),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (!compact) ...[
                SizedBox(width: 248, child: _History(state: state)),
                const SizedBox(width: 18),
              ],
              Expanded(
                child: _Thread(state: state, scroll: _scroll, input: _input, onSend: _send),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _History extends StatelessWidget {
  const _History({required this.state});
  final ChatState state;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final cubit = context.read<ChatCubit>();
    return GlassCard(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          MagnusButton(
            label: 'Nueva conversación',
            icon: context.icons.add,
            onTap: state.sending ? null : cubit.newConversation,
          ),
          const SizedBox(height: 14),
          Text('HISTORIAL',
              style: t.small.copyWith(fontSize: 10.5, letterSpacing: 1.2, color: t.textFaint)),
          const SizedBox(height: 8),
          Expanded(
            child: state.conversations.isEmpty
                ? Text('Aún no hay conversaciones.', style: t.small)
                : ListView.separated(
                    itemCount: state.conversations.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 4),
                    itemBuilder: (context, i) {
                      final c = state.conversations[i];
                      final selected = c.id == state.activeId;
                      return _HistoryItem(
                        title: c.title,
                        subtitle: c.model,
                        selected: selected,
                        onTap: () => cubit.open(c.id),
                        onDelete: () => cubit.delete(c.id),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

class _HistoryItem extends StatefulWidget {
  const _HistoryItem({
    required this.title,
    required this.subtitle,
    required this.selected,
    required this.onTap,
    required this.onDelete,
  });
  final String title;
  final String subtitle;
  final bool selected;
  final VoidCallback onTap;
  final VoidCallback onDelete;

  @override
  State<_HistoryItem> createState() => _HistoryItemState();
}

class _HistoryItemState extends State<_HistoryItem> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: widget.onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
          decoration: BoxDecoration(
            color: widget.selected ? t.accentSoft : (_hover ? t.surfaceAlt : const Color(0x00000000)),
            borderRadius: BorderRadius.circular(t.radius),
          ),
          child: Row(
            children: [
              Icon(context.icons.chat,
                  size: 15, color: widget.selected ? t.accent : t.textMuted),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(widget.title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: t.body.copyWith(
                            color: widget.selected ? t.accent : t.text,
                            fontWeight: widget.selected ? FontWeight.w600 : FontWeight.w400)),
                    Text(widget.subtitle,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: t.small.copyWith(fontSize: 11, color: t.textFaint)),
                  ],
                ),
              ),
              if (_hover)
                GestureDetector(
                  onTap: widget.onDelete,
                  child: Icon(context.icons.delete, size: 14, color: t.textFaint),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Thread extends StatelessWidget {
  const _Thread({
    required this.state,
    required this.scroll,
    required this.input,
    required this.onSend,
  });
  final ChatState state;
  final ScrollController scroll;
  final TextEditingController input;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final cubit = context.read<ChatCubit>();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        GlassCard(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 6,
                runSpacing: 6,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Text('Dónde', style: t.small),
                  ChoiceChipX(
                    label: 'Este equipo',
                    icon: context.icons.gpu,
                    selected: state.provider == null,
                    onTap: () => cubit.selectProvider(null),
                  ),
                  for (final p in state.providers.where((p) => p.enabled))
                    ChoiceChipX(
                      label: p.name,
                      icon: p.location == 'lan' ? context.icons.network : context.icons.cloud,
                      selected: p.id == state.provider,
                      onTap: () => cubit.selectProvider(p.id),
                    ),
                  if (state.providerLocation != 'local') ...[
                    const SizedBox(width: 4),
                    LocationChip(state.providerLocation),
                  ],
                ],
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Icon(context.icons.bolt, size: 16, color: state.model == null ? t.warn : t.ok),
                  const SizedBox(width: 8),
                  Text('Modelo', style: t.small),
                  const SizedBox(width: 10),
                  Expanded(
                    child: SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(
                        children: [
                          if (state.modelIds.isEmpty)
                            Text(
                                state.provider == null
                                    ? 'sin modelos descargados'
                                    : 'el proveedor no ofrece modelos',
                                style: t.small.copyWith(color: t.warn)),
                          for (final id in state.modelIds)
                            Padding(
                              padding: const EdgeInsets.only(right: 6),
                              child: ChoiceChipX(
                                label: id,
                                selected: id == state.model,
                                onTap: () => cubit.selectModel(id),
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Pill('${state.tokens} tokens', color: t.info, icon: context.icons.credits),
                  const SizedBox(width: 8),
                  Pill('${formatUsd(state.savings)} ahorro', color: Brand.amber, icon: context.icons.savings),
                ],
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Text('Documentos', style: t.small),
                  ChoiceChipX(
                    label: 'ninguno',
                    selected: state.collection == null,
                    onTap: () => cubit.selectCollection(null),
                  ),
                  for (final c in state.collections)
                    ChoiceChipX(
                      label: c.name,
                      icon: context.icons.documents,
                      selected: c.name == state.collection,
                      onTap: () => cubit.selectCollection(c.name),
                    ),
                  const SizedBox(width: 12),
                  Text('Razonar', style: t.small),
                  ChoiceChipX(label: 'auto', selected: state.think == null, onTap: () => cubit.setThink(null)),
                  ChoiceChipX(label: 'no', selected: state.think == false, onTap: () => cubit.setThink(false)),
                  ChoiceChipX(label: 'sí', selected: state.think == true, onTap: () => cubit.setThink(true)),
                ],
              ),
            ],
          ),
        ),
        if (state.error != null) ...[
          const SizedBox(height: 10),
          InlineNotice(state.error!, onClose: cubit.dismissError),
        ],
        const SizedBox(height: 14),
        Expanded(
          child: state.messages.isEmpty
              ? (state.models.isEmpty
                  ? EmptyState(
                      icon: context.icons.download,
                      title: 'Descarga un modelo para empezar',
                      message: 'En Modelos → Para este equipo verás los que caben en tu hardware.',
                    )
                  : _Welcome(onPick: (texto) => context.read<ChatCubit>().send(texto)))
              : ListView.builder(
                  controller: scroll,
                  itemCount: state.messages.length,
                  itemBuilder: (context, i) => _Bubble(state.messages[i]),
                ),
        ),
        const SizedBox(height: 14),
        _Composer(input: input, onSend: onSend, enabled: !state.sending),
      ],
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble(this.msg);
  final ChatBubble msg;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final isUser = msg.isUser;
    final tags = [...msg.skills, ...msg.sources];
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        constraints: const BoxConstraints(maxWidth: 640),
        child: Column(
          crossAxisAlignment: isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
          children: [
            if (tags.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Wrap(
                  spacing: 6,
                  runSpacing: 4,
                  children: [for (final tag in tags) Pill(tag, color: t.info)],
                ),
              ),
            if (msg.thinking.isNotEmpty) _Thinking(msg: msg),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: isUser ? t.accent : t.surfaceStrong,
                borderRadius: BorderRadius.only(
                  topLeft: Radius.circular(t.radiusLg),
                  topRight: Radius.circular(t.radiusLg),
                  bottomLeft: Radius.circular(isUser ? t.radiusLg : 4),
                  bottomRight: Radius.circular(isUser ? 4 : t.radiusLg),
                ),
                border: isUser ? null : Border.all(color: t.stroke),
              ),
              child: msg.text.isEmpty && msg.streaming
                  ? Text(msg.thinking.isEmpty ? 'Cargando el modelo…' : 'Razonando…',
                      style: t.body.copyWith(color: t.textMuted))
                  : isUser
                      // Lo que escribe la persona se respeta tal cual: si pega
                      // código o asteriscos, no se los reinterpreta nadie.
                      ? SelectableText(msg.text, style: t.body.copyWith(color: t.onAccent))
                      : MarkdownText(msg.streaming ? '${msg.text}▍' : msg.text),
            ),
            if (msg.error != null) ...[
              const SizedBox(height: 6),
              InlineNotice(msg.error!),
            ],
            if (msg.metrics != null) _MetricsLine(msg.metrics!),
          ],
        ),
      ),
    );
  }
}

class _Thinking extends StatefulWidget {
  const _Thinking({required this.msg});
  final ChatBubble msg;
  @override
  State<_Thinking> createState() => _ThinkingState();
}

class _ThinkingState extends State<_Thinking> {
  bool _open = false;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final text = widget.msg.thinking.trim();
    final preview = text.length > 160 ? '…${text.substring(text.length - 160)}' : text;
    return GestureDetector(
      onTap: () => setState(() => _open = !_open),
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        child: Container(
          margin: const EdgeInsets.only(bottom: 6),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: t.surfaceAlt,
            borderRadius: BorderRadius.circular(t.radius),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(context.icons.brain, size: 13, color: t.textFaint),
                  const SizedBox(width: 6),
                  Text(
                      widget.msg.streaming && widget.msg.text.isEmpty
                          ? 'Razonando…'
                          : 'Razonamiento (${text.length} caracteres) · ${_open ? 'ocultar' : 'ver'}',
                      style: t.small.copyWith(color: t.textFaint)),
                ],
              ),
              if (_open || (widget.msg.streaming && widget.msg.text.isEmpty)) ...[
                const SizedBox(height: 4),
                Text(_open ? text : preview,
                    style: t.small.copyWith(fontStyle: FontStyle.italic, color: t.textMuted)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _MetricsLine extends StatelessWidget {
  const _MetricsLine(this.m);
  final TurnMetrics m;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final saving = m.savingsUsd;
    final parts = <String>[
      '${m.tokensOut} tok',
      if (m.tokensPerS != null) '${m.tokensPerS!.toStringAsFixed(0)} tok/s',
      if (m.ttftS != null) '1er token ${m.ttftS!.toStringAsFixed(2)} s',
      if (m.avgPowerW != null) '${m.avgPowerW!.toStringAsFixed(1)} W',
      if (m.isRemote)
        m.providerCostUsd == null ? 'sin coste' : 'cobrado ${formatUsd(m.providerCostUsd!)}'
      else
        'local ${formatUsd(m.localCostUsd)}',
      '${m.cloudReference} ${formatUsd(m.cloudCostUsd)}',
    ];
    return Padding(
      padding: const EdgeInsets.only(top: 6, left: 4),
      child: Wrap(
        crossAxisAlignment: WrapCrossAlignment.center,
        spacing: 8,
        runSpacing: 4,
        children: [
          if (m.isRemote) LocationChip(m.location, providerName: m.provider),
          Text(parts.join(' · '), style: t.small.copyWith(fontSize: 11, color: t.textFaint)),
          // El ahorro es la única cifra en ámbar (docs/INFORME_PRODUCTO.md §8.2).
          Text(saving >= 0 ? 'ahorro ${formatUsd(saving)}' : 'sobrecoste ${formatUsd(-saving)}',
              style: t.small.copyWith(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: saving >= 0 ? Brand.amber : Brand.coral)),
        ],
      ),
    );
  }
}

class _Composer extends StatelessWidget {
  const _Composer({required this.input, required this.onSend, required this.enabled});
  final TextEditingController input;
  final VoidCallback onSend;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return GlassCard(
      padding: const EdgeInsets.fromLTRB(16, 6, 8, 6),
      strong: true,
      child: Row(
        children: [
          Expanded(
            // Enter envía; Shift+Enter hace salto de línea.
            child: Focus(
              onKeyEvent: (node, event) {
                if (event is KeyDownEvent &&
                    event.logicalKey == LogicalKeyboardKey.enter &&
                    !HardwareKeyboard.instance.isShiftPressed) {
                  if (enabled) onSend();
                  return KeyEventResult.handled;
                }
                return KeyEventResult.ignored;
              },
              child: TextField(
                controller: input,
                style: TextStyle(color: t.text, fontSize: 14),
                minLines: 1,
                maxLines: 6,
                decoration: InputDecoration(
                  isDense: true,
                  border: InputBorder.none,
                  hintText: enabled ? 'Escribe un mensaje a Magnus…' : 'Magnus está respondiendo…',
                  hintStyle: TextStyle(color: t.textFaint),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: enabled ? onSend : null,
            child: Opacity(
              opacity: enabled ? 1 : 0.45,
              child: Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: t.accent,
                  borderRadius: BorderRadius.circular(t.radius),
                ),
                child: Icon(context.icons.send, color: t.onAccent, size: 18),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Bienvenida del chat: saluda y propone por dónde empezar.
///
/// Las sugerencias no son decorado: en un asistente local la primera pregunta
/// suele ser «¿y esto qué sabe hacer?», y una lista corta responde mejor que un
/// párrafo. Al tocar una, se envía tal cual.
class _Welcome extends StatelessWidget {
  const _Welcome({required this.onPick});

  final ValueChanged<String> onPick;

  static const _sugerencias = [
    ('Explícame qué hace este equipo', 'Explícame en tres líneas qué puede hacer Magnus en mi equipo.'),
    ('Ayúdame a escribir', 'Ayúdame a escribir un correo breve y claro para pedir una reunión.'),
    ('Resume un texto', 'Te voy a pegar un texto y quiero un resumen en cinco viñetas.'),
    ('Dame ideas', 'Dame cinco ideas para organizar mejor mi semana de trabajo.'),
    ('Explícame un concepto', '¿Qué es la cuantización de un modelo y por qué me importa?'),
  ];

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final hora = DateTime.now().hour;
    final saludo = hora < 12 ? 'Buenos días' : (hora < 20 ? 'Buenas tardes' : 'Buenas noches');
    return Center(
      child: SingleChildScrollView(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 620),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ShaderMask(
                shaderCallback: (rect) => t.brandGradient.createShader(rect),
                child: Text(saludo, style: t.display.copyWith(color: const Color(0xFFFFFFFF))),
              ),
              const SizedBox(height: 6),
              Text('¿En qué te echo una mano? Todo corre aquí, en tu equipo.',
                  style: t.body.copyWith(color: t.textMuted)),
              const SizedBox(height: 22),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  for (final (etiqueta, prompt) in _sugerencias)
                    _Suggestion(label: etiqueta, onTap: () => onPick(prompt)),
                ],
              ),
              const SizedBox(height: 22),
              Row(
                children: [
                  Icon(context.icons.tip, size: 14, color: t.textFaint),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Escribe /resumir o /traducir para usar una skill, y cambia cómo te habla '
                      'Magnus en Ajustes → Personalidad.',
                      style: t.small.copyWith(color: t.textFaint),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Suggestion extends StatefulWidget {
  const _Suggestion({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  State<_Suggestion> createState() => _SuggestionState();
}

class _SuggestionState extends State<_Suggestion> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 140),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: _hover ? t.surfaceStrong : t.surfaceAlt,
            borderRadius: BorderRadius.circular(999),
            border: Border.all(color: _hover ? t.accent : t.stroke),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(context.icons.sparkle, size: 14, color: t.accent),
              const SizedBox(width: 8),
              Text(widget.label, style: t.small.copyWith(color: t.text)),
            ],
          ),
        ),
      ),
    );
  }
}
