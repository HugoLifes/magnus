import 'package:flutter/material.dart'
    show Material, Colors, TextField, InputDecoration, InputBorder, TextInputAction;
import 'package:flutter/widgets.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../../core/responsive/breakpoints.dart';
import '../../../../core/theme/magnus_theme.dart';
import '../../../../shared/widgets/ui.dart';

/// Mensaje de chat (modelo local; el transporte real será el WS `/chat`).
class _Msg {
  _Msg(this.role, this.text);
  final String role; // 'user' | 'assistant'
  final String text;
}

class _Conversation {
  _Conversation(this.title, this.messages);
  final String title;
  final List<_Msg> messages;
}

/// Sección de Chat: historial de conversaciones + hilo + compositor.
/// El envío real se conectará al WebSocket `/chat` del daemon (Fase 1); por
/// ahora la UI gestiona el estado local y deja el punto de integración listo.
class ChatPage extends StatefulWidget {
  const ChatPage({super.key});
  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  int _active = 0;
  int _tokens = 0;

  late final List<_Conversation> _convos = [
    _Conversation('Nueva conversación', [
      _Msg('assistant',
          'Hola 👋 Soy Magnus. Cuando conectes el daemon con un modelo montado, '
          'tus mensajes se transmitirán por streaming aquí.'),
    ]),
  ];

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _send() {
    final text = _input.text.trim();
    if (text.isEmpty) return;
    setState(() {
      _convos[_active].messages.add(_Msg('user', text));
      _convos[_active].messages.add(_Msg('assistant',
          '⏳ Pendiente: conecta el endpoint `/chat` del daemon para recibir la respuesta del modelo.'));
      _tokens += (text.length / 4).ceil(); // estimación simple de tokens
      _input.clear();
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(_scroll.position.maxScrollExtent,
            duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
      }
    });
  }

  void _newConversation() {
    setState(() {
      _convos.insert(0, _Conversation('Nueva conversación', []));
      _active = 0;
    });
  }

  @override
  Widget build(BuildContext context) {
    final compact = Breakpoints.of(context) == ScreenSize.compact;
    return Material(
      color: Colors.transparent,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 22, 20, 20),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (!compact) ...[
              SizedBox(width: 248, child: _History(
                convos: _convos,
                active: _active,
                onSelect: (i) => setState(() => _active = i),
                onNew: _newConversation,
              )),
              const SizedBox(width: 18),
            ],
            Expanded(child: _Thread(
              convo: _convos[_active],
              scroll: _scroll,
              input: _input,
              tokens: _tokens,
              onSend: _send,
            )),
          ],
        ),
      ),
    );
  }
}

class _History extends StatelessWidget {
  const _History({
    required this.convos,
    required this.active,
    required this.onSelect,
    required this.onNew,
  });
  final List<_Conversation> convos;
  final int active;
  final ValueChanged<int> onSelect;
  final VoidCallback onNew;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return GlassCard(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          MagnusButton(
            label: 'Nueva conversación',
            icon: LucideIcons.plus,
            onTap: onNew,
          ),
          const SizedBox(height: 14),
          Text('HISTORIAL',
              style: t.small.copyWith(
                  fontSize: 10.5, letterSpacing: 1.2, color: t.textFaint)),
          const SizedBox(height: 8),
          Expanded(
            child: ListView.separated(
              itemCount: convos.length,
              separatorBuilder: (_, __) => const SizedBox(height: 4),
              itemBuilder: (context, i) {
                final selected = i == active;
                final c = convos[i];
                return GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: () => onSelect(i),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 10),
                    decoration: BoxDecoration(
                      color: selected ? t.accentSoft : const Color(0x00000000),
                      borderRadius: BorderRadius.circular(t.radius),
                    ),
                    child: Row(
                      children: [
                        Icon(LucideIcons.messageCircle,
                            size: 15,
                            color: selected ? t.accent : t.textMuted),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            c.title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: t.body.copyWith(
                                color: selected ? t.accent : t.text,
                                fontWeight: selected
                                    ? FontWeight.w600
                                    : FontWeight.w400),
                          ),
                        ),
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
  }
}

class _Thread extends StatelessWidget {
  const _Thread({
    required this.convo,
    required this.scroll,
    required this.input,
    required this.tokens,
    required this.onSend,
  });
  final _Conversation convo;
  final ScrollController scroll;
  final TextEditingController input;
  final int tokens;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return Column(
      children: [
        // Barra superior: modelo + medidor de tokens (diferenciador)
        GlassCard(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Icon(LucideIcons.zap, size: 16, color: t.warn),
              const SizedBox(width: 8),
              Text('Sin modelo cargado',
                  style: t.body.copyWith(fontWeight: FontWeight.w600)),
              const Spacer(),
              Pill('$tokens tokens', color: t.info, icon: LucideIcons.coins),
              const SizedBox(width: 8),
              Pill(r'$0.00 ahorro', color: t.ok, icon: LucideIcons.piggyBank),
            ],
          ),
        ),
        const SizedBox(height: 14),
        Expanded(
          child: convo.messages.isEmpty
              ? const EmptyState(
                  icon: LucideIcons.messagesSquare,
                  title: 'Empieza a chatear',
                  message:
                      'Escribe un mensaje abajo. Se transmitirá al modelo montado '
                      'cuando el daemon exponga el endpoint de chat.',
                )
              : ListView.builder(
                  controller: scroll,
                  itemCount: convo.messages.length,
                  itemBuilder: (context, i) => _Bubble(convo.messages[i]),
                ),
        ),
        const SizedBox(height: 14),
        _Composer(input: input, onSend: onSend),
      ],
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble(this.msg);
  final _Msg msg;
  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    final isUser = msg.role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        constraints: const BoxConstraints(maxWidth: 560),
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
        child: Text(msg.text,
            style: t.body.copyWith(color: isUser ? t.onAccent : t.text)),
      ),
    );
  }
}

class _Composer extends StatelessWidget {
  const _Composer({required this.input, required this.onSend});
  final TextEditingController input;
  final VoidCallback onSend;
  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return GlassCard(
      padding: const EdgeInsets.fromLTRB(16, 6, 8, 6),
      strong: true,
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: input,
              style: TextStyle(color: t.text, fontSize: 14),
              minLines: 1,
              maxLines: 5,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => onSend(),
              decoration: InputDecoration(
                isDense: true,
                border: InputBorder.none,
                hintText: 'Escribe un mensaje a Magnus…',
                hintStyle: TextStyle(color: t.textFaint),
              ),
            ),
          ),
          const SizedBox(width: 8),
          _SendButton(onTap: onSend),
        ],
      ),
    );
  }
}

class _SendButton extends StatelessWidget {
  const _SendButton({required this.onTap});
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) {
    final t = MagnusTheme.of(context);
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          color: t.accent,
          borderRadius: BorderRadius.circular(t.radius),
        ),
        child: Icon(LucideIcons.send, color: t.onAccent, size: 18),
      ),
    );
  }
}
