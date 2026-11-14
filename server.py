import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.landscapeLeft,
    DeviceOrientation.landscapeRight,
  ]);
  runApp(const MicrostackMI7App());
}

class MicrostackMI7App extends StatelessWidget {
  const MicrostackMI7App({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Microstack V7.1.5',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF2B2E33),
      ),
      home: const MI7HomeScreen(),
    );
  }
}

class MI7HomeScreen extends StatefulWidget {
  const MI7HomeScreen({super.key});

  @override
  State<MI7HomeScreen> createState() => _MI7HomeScreenState();
}

class _MI7HomeScreenState extends State<MI7HomeScreen> {
  String _serverIp = "10.31.11.192";
  bool _isConnected = false;
  bool _isPlaying = false;
  bool _vocalOff = false;
  bool _repeat = false;
  double _volume = 80;
  int _queueCount = 0;
  Map<String, dynamic>? _currentSong;

  String _screenMode = "HOME";
  String _listTitle = "";
  List<dynamic> _items = [];
  bool _isLoading = false;
  String _numberInput = "";
  final TextEditingController _searchCtrl = TextEditingController();

  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _loadIp();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) => _fetchStatus());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _loadIp() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _serverIp = prefs.getString('server_ip') ?? "10.31.11.192";
    });
  }

  Future<void> _saveIp(String ip) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('server_ip', ip);
    setState(() => _serverIp = ip);
  }

  String get baseUrl => "http://$_serverIp:8000";

  Future<void> _fetchStatus() async {
    try {
      final res = await http.get(Uri.parse("$baseUrl/status")).timeout(const Duration(seconds: 2));
      if (res.statusCode == 200) {
        final data = json.decode(utf8.decode(res.bodyBytes));
        setState(() {
          _isConnected = true;
          _isPlaying = data['is_playing'] ?? false;
          _currentSong = data['current_song'];
          _vocalOff = data['vocal_off'] ?? false;
          _repeat = data['repeat'] ?? false;
          _queueCount = data['queue_count'] ?? 0;
          if (data['volume'] != null && data['volume'] >= 0) {
            _volume = (data['volume'] as num).toDouble().clamp(0, 100);
          }
        });
      }
    } catch (_) {
      if (_isConnected) setState(() => _isConnected = false);
    }
  }

  Future<void> _control(String action, {int value = 0}) async {
    try {
      await http.post(Uri.parse("$baseUrl/control/$action?value=$value"));
      _fetchStatus();
    } catch (_) {}
  }

  Future<void> _loadData(String mode, String title, String endpoint) async {
    setState(() {
      _screenMode = mode;
      _listTitle = title;
      _isLoading = true;
      _items = [];
    });
    try {
      final res = await http.get(Uri.parse("$baseUrl$endpoint"));
      if (res.statusCode == 200) {
        setState(() {
          _items = json.decode(utf8.decode(res.bodyBytes));
          _isLoading = false;
        });
      }
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _addSong(String id) async {
    try {
      final res = await http.post(Uri.parse("$baseUrl/queue/add/$id"));
      if (res.statusCode == 200) {
        _fetchStatus();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text("ကုဒ်နံပါတ် ($id) ကို လက်ရွေးစင်ထဲ ထည့်ပြီးပါပြီ"), duration: const Duration(seconds: 1)),
          );
        }
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text("ကုဒ်နံပါတ် ($id) ဗီဒီယိုဖိုင် စက်ထဲတွင် မတွေ့ပါ"), backgroundColor: Colors.red),
          );
        }
      }
    } catch (_) {}
  }

  void _showIpDialog() {
    final ctrl = TextEditingController(text: _serverIp);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1F2429),
        title: const Text("PC Server IP ချိတ်ဆက်ရန်", style: TextStyle(color: Colors.tealAccent)),
        content: TextField(
          controller: ctrl,
          decoration: const InputDecoration(labelText: "PC IP Address", border: OutlineInputBorder()),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text("ပိတ်မည်")),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.tealAccent, foregroundColor: Colors.black),
            onPressed: () {
              _saveIp(ctrl.text.trim());
              Navigator.pop(ctx);
            },
            child: const Text("ချိတ်ဆက်မည်"),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              colors: [Color(0xFF3A3F45), Color(0xFF23272B)],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
          ),
          child: Column(
            children: [
              _buildTopBar(),
              Expanded(child: _buildMainContent()),
              _buildBottomControlBar(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTopBar() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      color: Colors.black26,
      child: Row(
        children: [
          const Text("Microstack", style: TextStyle(color: Color(0xFF00E676), fontSize: 20, fontWeight: FontWeight.bold, fontStyle: FontStyle.italic)),
          const SizedBox(width: 6),
          const Text("V7.1.5", style: TextStyle(color: Colors.white70, fontSize: 12)),
          const SizedBox(width: 12),
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.white,
              foregroundColor: Colors.black87,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            ),
            icon: const Icon(Icons.playlist_play, color: Colors.green, size: 20),
            label: Text("လက်ရွေးစင် ($_queueCount)", style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
            onPressed: () => _loadData("QUEUE", "လက်ရွေးစင် သီချင်းစာရင်း", "/queue"),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(color: Colors.black45, borderRadius: BorderRadius.circular(8)),
              child: Text(
                _currentSong != null
                    ? "ဖွင့်နေသည်: [${_currentSong!['id']}] ${_currentSong!['title']} - ${_currentSong!['artist']}"
                    : "ရွေးချယ်ထားသော သီချင်းမရှိသေးပါ",
                style: const TextStyle(color: Colors.tealAccent, fontSize: 13),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ),
          const SizedBox(width: 10),
          GestureDetector(
            onTap: _showIpDialog,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: _isConnected ? Colors.green.shade800 : Colors.red.shade800,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(_isConnected ? Icons.wifi : Icons.wifi_off, size: 16, color: Colors.white),
                  const SizedBox(width: 4),
                  Text(_isConnected ? "Connected" : "IP ချိတ်ရန်", style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMainContent() {
    if (_screenMode == "HOME" || _screenMode == "SUB_MYANMAR") {
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Row(
              children: [
                _mi7CategoryCard("မြန်မာသီချင်းများ", "မြန်မာ", const Color(0xFF00796B), () {
                  setState(() => _screenMode = _screenMode == "SUB_MYANMAR" ? "HOME" : "SUB_MYANMAR");
                }),
                _mi7CategoryCard("China Song", "中文歌", const Color(0xFF37474F), () {
                  _loadData("LIST_SONGS", "China Songs", "/search?q=");
                }),
                _mi7CategoryCard("English Songs", "ENGLISH", const Color(0xFF37474F), () {
                  _loadData("LIST_SONGS", "English Songs", "/search?q=");
                }),
                _mi7CategoryCard("ရှမ်း၊ ကချင်၊ ရခိုင်\nကရင်၊ ပအိုဝ်", "တိုင်းရင်းသား", const Color(0xFF00695C), () {
                  _loadData("LIST_SONGS", "တိုင်းရင်းသား သီချင်းများ", "/search?q=");
                }),
                _mi7CategoryCard("Japan|Korea|Thai\nVietnam|India", "INTERNATIONAL", const Color(0xFF37474F), () {
                  _loadData("LIST_SONGS", "International Songs", "/search?q=");
                }),
                _mi7CategoryCard("Disco Songs", "DISCO", const Color(0xFF37474F), () {
                  _loadData("LIST_SONGS", "Disco Songs", "/search?q=");
                }),
                _mi7CategoryCard("Number Input", "NUMBER", const Color(0xFF00838F), () {
                  setState(() {
                    _numberInput = "";
                    _screenMode = "NUMBER_PAD";
                  });
                }),
              ],
            ),
            if (_screenMode == "SUB_MYANMAR") ...[
              const SizedBox(height: 14),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _mi7SubCard(Icons.person, "အဆိုတော်", Colors.pink.shade700, () {
                    _searchCtrl.clear();
                    _loadData("LIST_ARTISTS", "အဆိုတော် စာရင်း", "/browse/artists");
                  }),
                  _mi7SubCard(Icons.album, "တေးစီးရီး", Colors.orange.shade800, () {
                    _searchCtrl.clear();
                    _loadData("LIST_ALBUMS", "တေးစီးရီး စာရင်း", "/browse/albums");
                  }),
                  _mi7SubCard(Icons.music_video, "သီချင်းအမည်", Colors.blue.shade700, () {
                    _searchCtrl.clear();
                    _loadData("LIST_SONGS", "သီချင်းအမည် စာရင်း", "/search?q=");
                  }),
                ],
              ),
            ],
          ],
        ),
      );
    }

    if (_screenMode == "NUMBER_PAD") {
      return _buildNumberPad();
    }

    return _buildListView();
  }

  Widget _mi7CategoryCard(String topText, String bottomText, Color color, VoidCallback onTap) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          height: 115,
          margin: const EdgeInsets.symmetric(horizontal: 4),
          padding: const EdgeInsets.all(6),
          decoration: BoxDecoration(
            gradient: LinearGradient(colors: [color, color.withOpacity(0.6)], begin: Alignment.topLeft, end: Alignment.bottomRight),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.tealAccent.withOpacity(0.5), width: 1.5),
            boxShadow: const [BoxShadow(color: Colors.black45, blurRadius: 4, offset: Offset(0, 3))],
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(topText, style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold), textAlign: TextAlign.center),
              const SizedBox(height: 10),
              Text(bottomText, style: const TextStyle(color: Colors.amberAccent, fontSize: 13, fontWeight: FontWeight.bold), textAlign: TextAlign.center),
            ],
          ),
        ),
      ),
    );
  }

  Widget _mi7SubCard(IconData icon, String label, Color color, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 140,
        height: 95,
        margin: const EdgeInsets.symmetric(horizontal: 8),
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: Colors.white54, width: 1.5),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 36, color: Colors.white),
            const SizedBox(height: 6),
            Text(label, style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold)),
          ],
        ),
      ),
    );
  }

  Widget _buildNumberPad() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 240,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(color: Colors.black54, borderRadius: BorderRadius.circular(12), border: Border.all(color: Colors.tealAccent)),
              child: Text(
                _numberInput.isEmpty ? "ကုဒ်နံပါတ် ရိုက်ပါ" : _numberInput,
                style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: _numberInput.isEmpty ? Colors.grey : Colors.amberAccent),
                textAlign: TextAlign.center,
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(backgroundColor: Colors.red.shade700, padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12)),
                  icon: const Icon(Icons.backspace),
                  label: const Text("ဖျက်မည်"),
                  onPressed: () {
                    if (_numberInput.isNotEmpty) {
                      setState(() => _numberInput = _numberInput.substring(0, _numberInput.length - 1));
                    }
                  },
                ),
                const SizedBox(width: 12),
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(backgroundColor: Colors.green.shade700, padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12)),
                  icon: const Icon(Icons.play_arrow),
                  label: const Text("ဖွင့်မည် (Add)"),
                  onPressed: () {
                    if (_numberInput.isNotEmpty) {
                      _addSong(_numberInput);
                      setState(() => _numberInput = "");
                    }
                  },
                ),
              ],
            ),
          ],
        ),
        const SizedBox(width: 30),
        SizedBox(
          width: 260,
          child: GridView.count(
            shrinkWrap: true,
            crossAxisCount: 3,
            childAspectRatio: 1.6,
            mainAxisSpacing: 6,
            crossAxisSpacing: 6,
            children: ["1", "2", "3", "4", "5", "6", "7", "8", "9", "C", "0", "OK"].map((key) {
              return ElevatedButton(
                style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF37474F)),
                onPressed: () {
                  if (key == "C") {
                    setState(() => _numberInput = "");
                  } else if (key == "OK") {
                    if (_numberInput.isNotEmpty) {
                      _addSong(_numberInput);
                      setState(() => _numberInput = "");
                    }
                  } else {
                    setState(() => _numberInput += key);
                  }
                },
                child: Text(key, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white)),
              );
            }).toList(),
          ),
        ),
      ],
    );
  }

  Widget _buildListView() {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          color: Colors.black38,
          child: Row(
            children: [
              IconButton(
                icon: const Icon(Icons.arrow_back, color: Colors.tealAccent),
                onPressed: () => setState(() => _screenMode = "SUB_MYANMAR"),
              ),
              Text(_listTitle, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.amberAccent)),
              const SizedBox(width: 20),
              if (_screenMode != "QUEUE")
                Expanded(
                  child: SizedBox(
                    height: 36,
                    child: TextField(
                      controller: _searchCtrl,
                      onChanged: (val) {
                        if (_screenMode == "LIST_ARTISTS") _loadData("LIST_ARTISTS", _listTitle, "/browse/artists?q=${Uri.encodeComponent(val)}");
                        if (_screenMode == "LIST_ALBUMS") _loadData("LIST_ALBUMS", _listTitle, "/browse/albums?q=${Uri.encodeComponent(val)}");
                        if (_screenMode == "LIST_SONGS") _loadData("LIST_SONGS", _listTitle, "/search?q=${Uri.encodeComponent(val)}");
                      },
                      decoration: InputDecoration(
                        hintText: "ရှာဖွေရန် ရိုက်ထည့်ပါ...",
                        contentPadding: const EdgeInsets.symmetric(horizontal: 12),
                        filled: true,
                        fillColor: Colors.black45,
                        prefixIcon: const Icon(Icons.search, size: 18),
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: BorderSide.none),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
        Expanded(
          child: _isLoading
              ? const Center(child: CircularProgressIndicator())
              : _items.isEmpty
                  ? const Center(child: Text("စာရင်း မတွေ့ပါ"))
                  : ListView.builder(
                      itemCount: _items.length,
                      itemBuilder: (ctx, idx) {
                        final item = _items[idx];
                        if (_screenMode == "LIST_ARTISTS" || _screenMode == "LIST_ALBUMS") {
                          return ListTile(
                            dense: true,
                            leading: CircleAvatar(radius: 14, backgroundColor: Colors.teal, child: Text("${idx + 1}", style: const TextStyle(fontSize: 11))),
                            title: Text(item.toString(), style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
                            trailing: const Icon(Icons.chevron_right, color: Colors.tealAccent),
                            onTap: () {
                              final qParam = _screenMode == "LIST_ARTISTS"
                                  ? "/browse/filter?artist=${Uri.encodeComponent(item.toString())}"
                                  : "/browse/filter?album=${Uri.encodeComponent(item.toString())}";
                              _loadData("LIST_SONGS", item.toString(), qParam);
                            },
                          );
                        }
                        if (_screenMode == "QUEUE") {
                          return ListTile(
                            dense: true,
                            leading: CircleAvatar(radius: 14, backgroundColor: Colors.amber, child: Text("${idx + 1}", style: const TextStyle(color: Colors.black, fontSize: 11))),
                            title: Text("[${item['id']}] ${item['title']}", style: const TextStyle(fontWeight: FontWeight.bold)),
                            subtitle: Text(item['artist'] ?? ""),
                            trailing: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                IconButton(
                                  icon: const Icon(Icons.vertical_align_top, color: Colors.greenAccent),
                                  onPressed: () async {
                                    await http.post(Uri.parse("$baseUrl/queue/priority/$idx"));
                                    _loadData("QUEUE", _listTitle, "/queue");
                                  },
                                ),
                                IconButton(
                                  icon: const Icon(Icons.delete, color: Colors.redAccent),
                                  onPressed: () async {
                                    await http.delete(Uri.parse("$baseUrl/queue/remove/$idx"));
                                    _loadData("QUEUE", _listTitle, "/queue");
                                  },
                                ),
                              ],
                            ),
                          );
                        }
                        final bool hasFile = item['has_file'] == true;
                        return ListTile(
                          dense: true,
                          leading: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                            decoration: BoxDecoration(
                              color: hasFile ? Colors.teal.shade800 : Colors.grey.shade800,
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(item['id'] ?? "", style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
                          ),
                          title: Text(item['title'] ?? "", style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: hasFile ? Colors.white : Colors.grey)),
                          subtitle: Text("${item['artist']} • ${item['album']}", style: const TextStyle(fontSize: 12, color: Colors.white60)),
                          trailing: IconButton(
                            icon: Icon(Icons.add_circle, color: hasFile ? Colors.tealAccent : Colors.grey, size: 28),
                            onPressed: () => _addSong(item['id']),
                          ),
                        );
                      },
                    ),
        ),
      ],
    );
  }

  Widget _buildBottomControlBar() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
      color: Colors.black54,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          _bottomBtn(_isPlaying ? Icons.pause : Icons.play_arrow, "Play/Pause", Colors.pinkAccent, () => _control("play_pause")),
          _bottomBtn(Icons.stop, "Stop", Colors.redAccent, () => _control("stop")),
          _bottomBtn(Icons.repeat, "Repeat", _repeat ? Colors.amber : Colors.purpleAccent, () => _control("repeat")),
          _bottomBtn(Icons.fast_rewind, "<<<<", Colors.lightBlueAccent, () => _control("rewind")),
          _bottomBtn(Icons.fast_forward, ">>>>", Colors.lightBlueAccent, () => _control("forward")),
          _bottomBtn(Icons.replay, "Re-Start", Colors.pink, () => _control("restart")),
          _bottomBtn(Icons.skip_next, "Next", Colors.pink, () => _control("next")),
          _bottomBtn(Icons.home, "HOME", Colors.greenAccent, () => setState(() => _screenMode = "HOME")),
          _bottomBtn(Icons.mic, _vocalOff ? "Music" : "Vocal", _vocalOff ? Colors.amber : Colors.pinkAccent, () => _control("vocal_toggle")),
          _bottomBtn(Icons.volume_down, "Vol-", Colors.cyanAccent, () {
            setState(() => _volume = (_volume - 10).clamp(0, 100));
            _control("volume", value: _volume.toInt());
          }),
          _bottomBtn(Icons.volume_up, "Vol+", Colors.cyanAccent, () {
            setState(() => _volume = (_volume + 10).clamp(0, 100));
            _control("volume", value: _volume.toInt());
          }),
          _bottomBtn(Icons.volume_off, "Mute", _volume == 0 ? Colors.red : Colors.blueGrey, () {
            setState(() => _volume = _volume == 0 ? 80 : 0);
            _control("volume", value: _volume.toInt());
          }),
        ],
      ),
    );
  }

  Widget _bottomBtn(IconData icon, String label, Color color, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: const BoxDecoration(color: Colors.white12, shape: BoxShape.circle),
            child: Icon(icon, color: color, size: 18),
          ),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(fontSize: 9, color: Colors.white70)),
        ],
      ),
    );
  }
}
