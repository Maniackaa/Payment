instruction = """
<p><strong>I Регистрация в сервисе </strong><strong>asu-</strong><strong>payme.</strong><strong>com</strong></p>
<ol>
<li>Предоставить ваш email. Дождаться внесения в базу.</li>
<li>Зарегистрироваться <a href="https://asu-payme.com/auth/signup/">https://asu-payme.com/auth/signup/</a></li>
<li>Авторизоваться в системе <a href="https://asu-payme.com/auth/login/">https://asu-payme.com/auth/login/</a></li>
<li>Создать ваш магазин Merchant и заполнить данные:</li>
</ol>
<p>- <span style="color: #993300;">name</span><sup>*</sup></p>
<p>- <span style="color: #993300;">endpoint</span><sup>*</sup> для отправки webhook о подтверждении оплаты</p>
<p>- <span style="color: #993300;">endpoint_withdraw</span><sup>*</sup> для отправки withdraw о подтверждении выплаты</p>
<p>- <span style="color: #993300;">secret_key</span><sup>*</sup></p>
<p>- <span style="color: #993300;">url</span> для возврата пользователя после подтверждения платежа. Будет использоваться при отсутствии <span style="color: green;">back_url</span>.</p>
<p>- <span style="color: #993300;">ip</span> адреса, с которых будут приниматься запросы по API. При пустом поле будут приниматься с любых адресов.</p>
<p><span style="color: #993300;">- Dump webhook data&nbsp;<span style="color: #000000;">экранирование ответа в webhook</span> </span></p>
<p>&nbsp;</p>
<p>Вашему магазину будет присвоен <strong>merchant_id</strong></p>
<p>В настоящий момент работает 3 метода оплаты:</p>
<p>Метод <strong>&ldquo;card-to-card&rdquo;</strong> (Перевод на карту)</p>
<p>Метод <strong>&ldquo;card_2&rdquo;</strong> (Пополнение баланса по реквизитам карты)</p>
<p>Метод <strong>&ldquo;m10_to_m10&rdquo;</strong> (Пополнение баланса на кошелек М10)</p>
<p>&nbsp;</p>
<p><strong>II Проведение оплаты</strong></p>
<p><strong>II.1 Метод card_2 (Пополнение баланса по реквизитам карты)</strong></p>
<p><strong>Вариант 1.</strong></p>
<p>Перенаправить пользователя на страницу <a href="https://asu-payme.com/invoice">https://asu-payme.com/invoice</a>/ c аргументами:</p>
<p>&nbsp;</p>
<table>
<tbody>
<tr>
<td>
<p><strong>arg</strong></p>
</td>
<td>
<p><strong>type</strong></p>
</td>
<td>
<p><strong>description</strong></p>
</td>
</tr>
<tr>
<td>
<p>merchant_id<sup>*</sup></p>
</td>
<td>
<p>Integer</p>
</td>
<td>
<p>id мерчанта</p>
</td>
</tr>
<tr>
<td>
<p>order_id<sup>*</sup></p>
</td>
<td>
<p>String(36)</p>
</td>
<td>
<p>идентификатор заказа</p>
</td>
</tr>
<tr>
<td>
<p>owner_name</p>
</td>
<td>
<p>String(100)</p>
</td>
<td>
<p>имя плательщика</p>
</td>
</tr>
<tr>
<td>
<p>user_login</p>
</td>
<td>
<p>String(36)</p>
</td>
<td>
<p>идентификатор пользователя</p>
</td>
</tr>
<tr>
<td>
<p>amount</p>
</td>
<td>
<p>Integer</p>
</td>
<td>
<p>сумма</p>
</td>
</tr>
<tr>
<td>
<p>pay_type<sup>*</sup></p>
</td>
<td>
<p>&ldquo;card_2&rdquo;</p>
</td>
<td>
<p>тип платежа</p>
</td>
</tr>
<tr>
<td>
<p>back_url</p>
</td>
<td>
<p>Url()</p>
</td>
<td>
<p>Ссылка для возврата</p>
</td>
</tr>
<tr>
<td>
<p>signature<sup>*</sup></p>
</td>
<td>
<p>String()</p>
</td>
<td>
<p>сигнатура</p>
</td>
</tr>
</tbody>
</table>
<p>&nbsp;</p>
<p>Пример:</p>
<p><a href="https://asu-payme.com/invoice/">https://asu-payme.com/invoice/</a></p>
<p>?merchant_id=1</p>
<p>&amp;order_id=xxxx-yyyy-zzz-12335</p>
<p>&amp;amount=5</p>
<p>&amp;owner_name=John%20Dou</p>
<p>&amp;user_login=user_22216456</p>
<p>&amp;pay_type=card_2</p>
<p>&amp;back_url=https://stackoverflow.com/questions/</p>
<p>&amp;signature=3ead5e8ae4762fc2baed99a18c754e0924667bd67156cd97f6a955f8e5017591</p>
<p>&nbsp;</p>
<p>Расчет signature:</p>
<p>string = merchant_id + order_id + secret_key (encoding UTF-8)</p>
<p><em>signature</em><em> = hash('sha256', $string)</em></p>
<p>В примере string = 1<em>xxxx-yyyy-zzz-12335</em><span style="color: #993300;">secret_key</span></p>
<p>&nbsp;</p>
<p>Далее пользователь действует по инструкции сайта. После <strong>подтверждения</strong> платежа на endpoint указанный при регистрации отправляется POST-запрос:</p>
<p>&nbsp;</p>
<p>POST endpoint</p>
<p>Content-Type: application/json</p>
<p>&nbsp;</p>
<p>{</p>
<p>&nbsp; "id": "65dba7ee-2e8a-46fd-88f2-9855fed36a39",&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; / идентификатор asu-payme</p>
<p>&nbsp; "order_id": " xxxx-yyyy-zzz-12335",</p>
<p>&nbsp; "user_login": "user_login",</p>
<p>&nbsp; "amount": 500.25,</p>
<p>&nbsp; "create_at": &ldquo;2024-05-16T08:50:17.092730&rdquo;, &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; / время создания isoformat</p>
<p>&nbsp; "status": 9, &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; / -1 отклонен, 9 подтвержден</p>
<p>&nbsp; "confirmed_time": 2024-05-16T08:51:17.092730, &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; / время подтверждения isoformat</p>
<p>&nbsp; "confirmed_amount": 400.25,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; / подтвержденная сумма</p>
<p>&nbsp; "signature": "59f232b7a2a22f9d1bf8829c6b39ab0b0410eba6a83d5fd402743ae0c415f6b1",</p>
<p>&nbsp; "mask": "1111**1234"</p>
<p>}</p>
<p>&nbsp;</p>
<p>Расчет signature (confirmed_amount берется только целая часть):</p>
<p>string = id + order_id + confirmed_amount + status + &nbsp;secret_key; (encoding UTF-8)</p>
<p><em>signature</em><em> = hash('sha256', $string)</em></p>
<p>В примере string:</p>
<p>65dba7ee-2e8a-46fd-88f2-9855fed36a39400xxxx-yyyy-zzz-123354009secret_key</p>
<p>&nbsp;</p>
<p>При <strong>отклонении</strong> платежа на endpoint указанный при регистрации отправляется POST-запрос:</p>
<p>&nbsp;</p>
<p>POST endpoint</p>
<p>Content-Type: application/json</p>
<p>&nbsp;</p>
<p>{</p>
<p>&nbsp; "id": "65dba7ee-2e8a-46fd-88f2-9855fed36a39",&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; / идентификатор asu-payme</p>
<p>&nbsp; "order_id": " xxxx-yyyy-zzz-12335",</p>
<p>&nbsp; "status": -1, &nbsp; &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; / -1 отклонен, 9 подтвержден</p>
<p>&nbsp; "signature": "360f92b7ebdb4a7a4671c8ee9df4fe755d91ebe8ede99e814cd22b3ad0aa1219"</p>
<p>}</p>
<p>&nbsp;</p>
<p>Расчет signature:</p>
<p>string = id + order_id + status + &nbsp;secret_key; (encoding UTF-8)</p>
<p><em>signature</em><em> = hash('sha256', $string)</em></p>
<p>В примере string:</p>
<p>65dba7ee-2e8a-46fd-88f2-9855fed36a39400xxxx-yyyy-zzz-12335-1secret_key</p>
<p>&nbsp;</p>
<p><strong>Вариант 2. Воспользоваться API:</strong></p>
<p>Для авторизации используется JWT Bearer Authorization.</p>
<p>ACCESS_TOKEN_LIFETIME: 1 hours</p>
<p>REFRESH_TOKEN_LIFETIME: 1 days</p>
<p>curl --location https://asu-payme.com/api/v1/payment/' \</p>
<p>--header 'Content-Type: application/json' \</p>
<p>--header 'Authorization: Bearer eyJhbGciOiJI&bull;&bull;&bull;&bull;&bull;&bull;' \</p>
<p>--data '{</p>
<p>&emsp;'merchant': '2',</p>
<p>&emsp;'order_id': 'test_id',</p>
<p>&emsp;'amount': '15',</p>
<p>&emsp;'pay_type': 'card_2'</p>
<p>}'</p>
<p>1. Отправка данных для создания платежа</p>
<p>2. Отправка даных карты</p>
<p>3. Отправка кода подтверждения из смс (при необходимости)</p>
<p>&nbsp;</p>
<p><strong>II.2 Метод card-to-card (Перевод на карту)</strong></p>
<p><strong>Вариант 1.</strong></p>
<p>Аналогичен методу II.1, за исключнием того, что amount является обязательным параметром.</p>
<p><strong>Вариант 2. Воспользоваться API:</strong></p>
<p>Для авторизации используется JWT Bearer Authorization.</p>
<p>1. Отправка данных для создания платежа. В ответ присылаются реквизиты для оплаты</p>
<p>&nbsp;</p>
<p>&nbsp;</p>
<p><strong>II.3 Метод <strong>m10_to_m10</strong> (Пополнение кошелька М10)</strong></p>
<p><strong>Вариант 1.</strong></p>
<p>Аналогичен методу II.1, за исключнием того, что amount является обязательным параметром.</p>
<p><strong>Вариант 2. Воспользоваться API:</strong></p>
<p>Для авторизации используется JWT Bearer Authorization.</p>
<p>1. Отправка данных для создания платежа.</p>
<p>2. Отправка телефона отправителя. В ответ присылаются реквизиты для оплаты.</p>
"""