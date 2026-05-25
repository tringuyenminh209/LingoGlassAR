import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

enum _ServerStatus { waiting, online, degraded, offline }

class ServerStatusChip extends StatefulWidget {
  const ServerStatusChip({
    super.key,
    this.apiBase,
    this.client,
  });

  final Uri? apiBase;

  /// Allows tests to drive status responses without opening a socket.
  final http.Client? client;

  @override
  State<ServerStatusChip> createState() => _ServerStatusChipState();
}

class _ServerStatusChipState extends State<ServerStatusChip> {
  static final Uri _defaultApiBase = Uri.parse('https://api.lingoglass.online');

  late final http.Client _client;
  late final bool _ownsClient;
  Timer? _timer;
  Timer? _requestTimeout;
  int _pollSequence = 0;
  int? _activePoll;
  _ServerStatus _status = _ServerStatus.waiting;

  @override
  void initState() {
    super.initState();
    _ownsClient = widget.client == null;
    _client = widget.client ?? http.Client();
    _poll();
    _timer = Timer.periodic(const Duration(seconds: 10), (_) => _poll());
  }

  void _poll() {
    if (_activePoll != null) {
      return;
    }
    final pollId = ++_pollSequence;
    _activePoll = pollId;
    _requestTimeout = Timer(
      const Duration(seconds: 5),
      () => _finishPoll(pollId, _ServerStatus.offline),
    );

    final base = widget.apiBase ?? _defaultApiBase;
    _client.get(base.resolve('/healthz')).then((response) {
      var status = _ServerStatus.offline;
      try {
        if (response.statusCode == 200) {
          final json = jsonDecode(response.body);
          if (json is Map<String, dynamic> && json['redis'] == 'up') {
            status = _ServerStatus.online;
          } else if (json is Map<String, dynamic> && json['redis'] == 'down') {
            status = _ServerStatus.degraded;
          }
        }
      } catch (_) {
        status = _ServerStatus.offline;
      }
      _finishPoll(pollId, status);
    }, onError: (_) => _finishPoll(pollId, _ServerStatus.offline));
  }

  void _finishPoll(int pollId, _ServerStatus nextStatus) {
    if (_activePoll != pollId) {
      return;
    }
    _activePoll = null;
    _requestTimeout?.cancel();
    _requestTimeout = null;
    if (mounted) {
      setState(() => _status = nextStatus);
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _requestTimeout?.cancel();
    _activePoll = null;
    if (_ownsClient) {
      _client.close();
    }
    super.dispose();
  }

  Color get _backgroundColor {
    return switch (_status) {
      _ServerStatus.waiting => Colors.grey.shade300,
      _ServerStatus.online => Colors.green.shade100,
      _ServerStatus.degraded => Colors.yellow.shade100,
      _ServerStatus.offline => Colors.red.shade100,
    };
  }

  Color get _borderColor {
    return switch (_status) {
      _ServerStatus.waiting => Colors.grey,
      _ServerStatus.online => Colors.green,
      _ServerStatus.degraded => Colors.yellow.shade700,
      _ServerStatus.offline => Colors.red,
    };
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Chip(
        label: const Text('API', style: TextStyle(fontSize: 10)),
        backgroundColor: _backgroundColor,
        side: BorderSide(color: _borderColor),
        padding: EdgeInsets.zero,
        visualDensity: VisualDensity.compact,
      ),
    );
  }
}
