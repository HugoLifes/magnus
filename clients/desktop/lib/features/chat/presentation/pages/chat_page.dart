import 'package:flutter/material.dart'
    show
        Colors,
        InputBorder,
        InputDecoration,
        Material,
        MaterialType,
        PopupMenuButton,
        PopupMenuItem,
        PopupMenuPosition,
        RoundedRectangleBorder,
        SelectableText,
        TextField;
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

  /// El historial se puede esconder: en una conversación larga, la pantalla
  /// entera para el hilo se agradece.
  bool _historial = true;

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
              if (!compact && _historial) ...[
                SizedBox(width: 248, child: _History(state: state)),
                const SizedBox(width: 18),
              ],
              Expanded(
                child: _Thread(
                  state: state,
                  scroll: _scroll,
                  input: _input,
                  onSend: _send,
                  historial: compact ? null : _historial,
                  onHistorial: () => setState(() => _historial = !_historial),
                ),
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
    required this.historial,
    required this.onHistorial,
  });
  final ChatState state;
  final ScrollController scroll;
  final TextEditingController input;
  final VoidCallback onSend;

  /// Si el historial está abierto; null en pantallas estrechas, donde no cabe.
  final bool? historial;
  final VoidCallback onHistorial;

  @override
  Widget build(BuildContext context) {
    final cubit = context.read<ChatCubit>();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (historial != null)
          Align(
            alignment: Alignment.centerLeft,
            child: _GhostButton(
              icon: historial! ? context.icons.panelCollapse : context.icons.panelExpand,
              label: historial! ? 'Ocultar conversaciones' : 'Conversaciones',
              onTap: onHistorial,
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
        const SizedBox(height: 12),
        _Composer(state: state, input: input, onSend: onSend),
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
  const _Composer({required this.state, required this.input, required this.onSend});

  final ChatState state;
  final TextEditingController input;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final enabled = !state.sending;
    return GlassCard(
      padding: const EdgeInsets.fromLTRB(14, 10, 10, 8),
      strong: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
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
                    style: TextStyle(color: t.text, fontSize: 14.5),
                    minLines: 1,
                    maxLines: 8,
                    decoration: InputDecoration(
                      isDense: true,
                      border: InputBorder.none,
                      hintText:
                          enabled ? 'Escribe un mensaje a Magnus…' : 'Magnus está respondiendo…',
                      hintStyle: TextStyle(color: t.textFaint),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              GestureDetector(
                onTap: enabled ? onSend : null,
                child: MouseRegion(
                  cursor: enabled ? SystemMouseCursors.click : SystemMouseCursors.basic,
                  child: Opacity(
                    opacity: enabled ? 1 : 0.45,
                    child: Container(
                      width: 38,
                      height: 38,
                      decoration: BoxDecoration(
                        gradient: t.brandGradient,
                        borderRadius: BorderRadius.circular(t.radius),
                      ),
                      child: Icon(context.icons.send, color: t.onAccent, size: 17),
                    ),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          _ComposerControls(state: state),
        ],
      ),
    );
  }
}

/// Los ajustes del turno, donde se escribe.
///
/// Antes vivían en una tarjeta arriba que se comía media pantalla para cosas
/// que se tocan una vez por conversación. Aquí ocupan una línea y se abren solo
/// cuando hacen falta, que es como funcionan los chats que la gente ya usa.
class _ComposerControls extends StatelessWidget {
  const _ComposerControls({required this.state});

  final ChatState state;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final cubit = context.read<ChatCubit>();
    final remoto = state.providerLocation != 'local';
    final donde = state.provider == null
        ? 'Este equipo'
        : state.providers
            .firstWhere((p) => p.id == state.provider,
                orElse: () => state.providers.first)
            .name;

    // Material transparente: los menús emergentes lo necesitan, y los tres
    // shells (Fluent, Material y macOS) no siempre lo traen encima.
    return Material(
      type: MaterialType.transparency,
      child: Row(
        children: [
          Expanded(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  _MenuChip(
                    label: state.model ?? 'sin modelo',
                    icon: context.icons.models,
                    tone: state.model == null ? t.warn : null,
                    options: [
                      for (final id in state.modelIds)
                        _Option(id, id, selected: id == state.model),
                    ],
                    empty: state.provider == null
                        ? 'Sin modelos descargados'
                        : 'El proveedor no ofrece modelos',
                    onSelected: cubit.selectModel,
                  ),
                  const SizedBox(width: 8),
                  _MenuChip(
                    label: donde,
                    icon: remoto ? context.icons.cloud : context.icons.gpu,
                    tone: remoto ? t.info : null,
                    options: [
                      _Option('', 'Este equipo', selected: state.provider == null),
                      for (final p in state.providers.where((p) => p.enabled))
                        _Option(p.id, p.name, selected: p.id == state.provider),
                    ],
                    onSelected: (id) => cubit.selectProvider(id.isEmpty ? null : id),
                  ),
                  const SizedBox(width: 8),
                  _MenuChip(
                    label: state.collection ?? 'Documentos',
                    icon: context.icons.documents,
                    tone: state.collection == null ? null : t.accent,
                    options: [
                      _Option('', 'Ninguno', selected: state.collection == null),
                      for (final c in state.collections)
                        _Option(c.name, c.name, selected: c.name == state.collection),
                    ],
                    empty: 'Todavía no tienes colecciones',
                    onSelected: (name) => cubit.selectCollection(name.isEmpty ? null : name),
                  ),
                  const SizedBox(width: 8),
                  _MenuChip(
                    label: switch (state.think) {
                      true => 'Razona',
                      false => 'Sin razonar',
                      _ => 'Razonar: auto',
                    },
                    icon: context.icons.brain,
                    options: [
                      _Option('auto', 'Auto (lo decide el modelo)', selected: state.think == null),
                      _Option('si', 'Razonar siempre', selected: state.think == true),
                      _Option('no', 'No razonar', selected: state.think == false),
                    ],
                    onSelected: (v) =>
                        cubit.setThink(v == 'auto' ? null : v == 'si'),
                  ),
                ],
              ),
            ),
          ),
          // El medidor, en pequeño: informa sin robar atención.
          if (state.tokens > 0) ...[
            const SizedBox(width: 10),
            Text('${state.tokens} tok', style: t.small.copyWith(color: t.textFaint)),
            const SizedBox(width: 8),
            Text(
              state.savings >= 0
                  ? '${formatUsd(state.savings)} ahorro'
                  : '${formatUsd(-state.savings)} de más',
              style: t.small.copyWith(
                  color: state.savings >= 0 ? Brand.amber : t.textFaint),
            ),
          ],
        ],
      ),
    );
  }
}

/// Una opción de un menú del compositor.
class _Option {
  const _Option(this.value, this.label, {this.selected = false});
  final String value;
  final String label;
  final bool selected;
}

/// Chip que abre un menú: el patrón de los chats modernos, sin barra fija.
class _MenuChip extends StatelessWidget {
  const _MenuChip({
    required this.label,
    required this.icon,
    required this.options,
    required this.onSelected,
    this.tone,
    this.empty,
  });

  final String label;
  final IconData icon;
  final List<_Option> options;
  final ValueChanged<String> onSelected;
  final Color? tone;
  final String? empty;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final color = tone ?? t.textMuted;
    final vacio = options.where((o) => o.value.isNotEmpty).isEmpty && empty != null;
    return PopupMenuButton<String>(
      tooltip: '',
      position: PopupMenuPosition.over,
      color: t.bgElevated,
      elevation: 8,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(t.radius),
        side: BorderSide(color: t.stroke),
      ),
      onSelected: onSelected,
      itemBuilder: (context) => [
        if (vacio)
          PopupMenuItem<String>(
            enabled: false,
            child: Text(empty!, style: t.small),
          )
        else
          for (final o in options)
            PopupMenuItem<String>(
              value: o.value,
              height: 38,
              child: Row(
                children: [
                  SizedBox(
                    width: 14,
                    child: o.selected
                        ? Icon(context.icons.check, size: 14, color: t.accent)
                        : null,
                  ),
                  const SizedBox(width: 10),
                  Text(o.label,
                      style: t.body.copyWith(
                          fontSize: 13,
                          fontWeight: o.selected ? FontWeight.w600 : FontWeight.w400)),
                ],
              ),
            ),
      ],
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: t.surfaceAlt,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: t.stroke),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 13, color: color),
            const SizedBox(width: 6),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 190),
              child: Text(label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: t.small.copyWith(color: t.text, fontSize: 12)),
            ),
            const SizedBox(width: 4),
            Icon(context.icons.chevronDown, size: 12, color: t.textFaint),
          ],
        ),
      ),
    );
  }
}

/// Botón de texto, sin fondo hasta que pasas por encima.
class _GhostButton extends StatefulWidget {
  const _GhostButton({required this.icon, required this.label, required this.onTap});

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  State<_GhostButton> createState() => _GhostButtonState();
}

class _GhostButtonState extends State<_GhostButton> {
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
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          margin: const EdgeInsets.only(bottom: 10),
          decoration: BoxDecoration(
            color: _hover ? t.stateLayer() : const Color(0x00000000),
            borderRadius: BorderRadius.circular(t.radiusSm),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(widget.icon, size: 15, color: t.textMuted),
              const SizedBox(width: 8),
              Text(widget.label, style: t.small.copyWith(color: t.textMuted)),
            ],
          ),
        ),
      ),
    );
  }
}

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
